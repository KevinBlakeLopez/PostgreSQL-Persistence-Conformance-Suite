# frozen_string_literal: true

# Shared PPCS adapter protocol for the Ruby adapters. This is not a conformance
# framework: it reads and writes the newline-delimited JSON in docs/protocol.md
# and injects the client-side faults the catalog already defines.
require 'json'
require 'timeout'

module Ppcs
  class ProtocolError < StandardError; end
  class InjectedFailure < StandardError; end

  # PostgreSQL answers COMMIT with command tag COMMIT or ROLLBACK. Both are
  # PGRES_COMMAND_OK. PQTRANS_IDLE after the call does not distinguish them.
  # cmd_status does. Any other tag, or a missing tag, is not enough evidence
  # for either outcome.
  module CommitOutcome
    def self.classify(mode, tag:, error:)
      if error
        if mode == 'unsafe'
          return { reported: 'rolled_back', basis: 'COMMIT raised an error, which the unsafe control reports as a rollback' }
        end
        return { reported: 'failed', basis: 'COMMIT raised an error; the control does not treat that as a confirmed rollback or a confirmed commit' }
      end

      normalized = tag&.strip
      if mode == 'correct'
        case normalized
        when 'COMMIT'
          { reported: 'committed', basis: 'COMMIT was answered with the command tag COMMIT' }
        when 'ROLLBACK'
          { reported: 'rolled_back', basis: 'COMMIT was answered with the command tag ROLLBACK' }
        else
          { reported: 'failed', basis: "COMMIT returned command tag #{normalized.inspect}, which is neither COMMIT nor ROLLBACK" }
        end
      else
        { reported: 'committed', basis: "COMMIT did not raise (command tag #{normalized})" }
      end
    end
  end

  ROLLBACK_SQL = /\Arollback;?\z/i
  SAVEPOINT_ROLLBACK_SQL = /\Arollback to (savepoint )?/i
  COMMIT_SQL = /\Acommit;?\z/i

  module Protocol
    def self.read
      while (line = $stdin.gets)
        begin
          msg = JSON.parse(line)
        rescue JSON::ParserError
          next
        end
        return msg if msg.is_a?(Hash) && msg['ppcs'] == 1
      end
      raise ProtocolError, 'the runner closed the protocol stream'
    end

    def self.send(msg)
      $stdout.write("#{JSON.generate({ 'ppcs' => 1 }.merge(msg))}\n")
      $stdout.flush
    end
  end

  def self.err_info(error)
    {
      'class' => error.class.name,
      'code' => sqlstate(error),
      'message' => error.message.to_s.split("\n").first
    }
  end

  def self.sqlstate(error)
    [error, (error.cause if error.respond_to?(:cause))].compact.each do |candidate|
      result = candidate.respond_to?(:result) ? candidate.result : nil
      next unless result.respond_to?(:error_field)
      code = result.error_field(PG::Result::PG_DIAG_SQLSTATE)
      return code if code
    end
    nil
  rescue StandardError
    nil
  end

  def self.connect(spec)
    params = {
      host: spec['host'],
      port: spec['port'],
      user: spec['user'],
      password: spec['password'],
      dbname: spec['database'],
      application_name: spec['application_name'],
      connect_timeout: 10
    }
    params[:options] = spec['options'] if spec['options']
    PG.connect(params)
  end

  def self.transaction_status_name(conn)
    current = conn.transaction_status
    names = {
      PG::PQTRANS_IDLE => 'idle',
      PG::PQTRANS_ACTIVE => 'active',
      PG::PQTRANS_INTRANS => 'intrans',
      PG::PQTRANS_INERROR => 'inerror',
      PG::PQTRANS_UNKNOWN => 'unknown'
    }
    names.fetch(current, current.to_s)
  rescue StandardError
    'unavailable'
  end

  # Statement trace and category C/D faults. Classification never reads the trace.
  # Faults run inside the driver's query method, before the caller sees the error.
  module Instrument
    TX_CONTROL = /\A(begin|start transaction|commit|end|rollback|savepoint|release)\b/i

    class << self
      attr_reader :entries, :faults, :installed

      def install!
        return if @installed
        require 'pg'
        @installed = true
        @entries = []
        @faults = []
        PG::Connection.prepend(Patch)
      end

      def add_fault(match:, mode:, rewrite: nil, on_fire: nil)
        fault = {
          match: match, mode: mode, rewrite: rewrite, on_fire: on_fire,
          once: true, used: false, fired: 0, reply_codes: []
        }
        @faults << fault
        fault
      end

      def clear_faults!
        @faults.clear
      end

      def savepoint_rollback_fault(kind, &on_fire)
        if kind == 'not-sent'
          add_fault(match: SAVEPOINT_ROLLBACK_SQL, mode: 'client-reject', on_fire: on_fire)
        else
          add_fault(
            match: SAVEPOINT_ROLLBACK_SQL,
            mode: 'rewrite',
            rewrite: ->(_sql) { 'ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint' },
            on_fire: on_fire
          )
        end
      end

      def fault_report(fault)
        return nil unless fault
        report = { 'mode' => fault[:mode], 'fired' => fault[:fired] }
        report['reply_codes'] = fault[:reply_codes].dup unless fault[:reply_codes].empty?
        report['hook_error'] = fault[:hook_error] if fault[:hook_error]
        report
      end

      def trace
        labels = {}
        @entries.map do |entry|
          pid = entry[:pid]
          if pid && !labels.key?(pid)
            labels[pid] = "c#{labels.size + 1}"
          end
          prefix = pid ? "#{labels[pid]}(pid #{pid})" : '??'
          "#{prefix}: #{entry[:sql]}"
        end
      end

      def commit_replies
        @entries.filter_map do |entry|
          next unless entry[:kind] == 'reply'
          match = entry[:sql].match(/command tag (\S+) for: (?:commit|end)\b/i)
          match && match[1]
        end
      end

      def apply(conn, sql)
        text = sql.to_s
        fault = @faults.find { |item| !item[:used] && item[:match].match?(text.strip) }
        if fault
          fault[:used] = true if fault[:once]
          fault[:fired] += 1
          return apply_fault(conn, fault, text) { |effective| yield effective }
        end
        record(conn, text)
        begin
          result = yield(text)
          observe_ok(conn, text, result)
          result
        rescue PG::Error => e
          record(conn, "-> ERROR #{Ppcs.sqlstate(e)} #{e.message.to_s.split("\n").first}", 'error')
          raise
        end
      end

      private

      def apply_fault(conn, fault, text)
        case fault[:mode]
        when 'client-reject'
          record(conn, "#{text}  -- INJECTED client-side failure, statement NOT sent", 'fault')
          fire(fault)
          raise InjectedFailure, "injected client-side failure for: #{text.strip[0, 60]}"
        when 'rewrite'
          rewritten = fault[:rewrite].call(text)
          record(conn, "#{rewritten}  -- INJECTED rewrite of: #{text.strip}", 'fault')
          begin
            result = yield(rewritten)
            fault[:reply_codes] << 'ok'
            fire(fault)
            result
          rescue PG::Error => e
            fault[:reply_codes] << (Ppcs.sqlstate(e) || 'error')
            fire(fault)
            raise
          end
        when 'reply-lost'
          record(conn, "#{text}  -- INJECTED (client-side simulation): sent, then the client closes its connection and discards the reply", 'fault')
          begin
            yield(text)
          rescue PG::Error
            nil
          end
          begin
            conn.close
          rescue StandardError
            nil
          end
          raise PG::ConnectionBad, "connection lost after sending: #{text.strip[0, 60]}"
        else
          raise ProtocolError, "unknown fault mode #{fault[:mode]}"
        end
      end

      def fire(fault)
        return unless fault[:on_fire]
        fault[:on_fire].call
      rescue StandardError => e
        fault[:hook_error] = e.message.to_s
        raise if e.is_a?(ProtocolError)
      end

      def record(conn, text, kind = 'sql')
        @entries << {
          pid: (conn.backend_pid rescue nil),
          sql: text.to_s.strip.gsub(/\s+/, ' ')[0, 300],
          kind: kind
        }
      end

      def observe_ok(conn, text, result)
        return unless text.strip.match?(TX_CONTROL)
        tag = result.respond_to?(:cmd_status) ? result.cmd_status : nil
        record(conn, "-> command tag #{tag} for: #{text.strip}", 'reply') if tag
      end
    end

    module Patch
      def exec(*args, &block)
        ppcs_query(args) { |rewritten| super(*rewritten, &block) }
      end

      def async_exec(*args, &block)
        ppcs_query(args) { |rewritten| super(*rewritten, &block) }
      end

      def exec_params(*args, &block)
        ppcs_query(args) { |rewritten| super(*rewritten, &block) }
      end

      def exec_prepared(*args, &block)
        # The first argument is a statement name, not SQL. Do not rewrite it.
        super
      end

      def query(*args, &block)
        ppcs_query(args) { |rewritten| super(*rewritten, &block) }
      end

      private

      def ppcs_query(args)
        sql = args[0]
        return yield(args) unless sql.is_a?(String)
        return yield(args) if Thread.current[:ppcs_reentry]
        Thread.current[:ppcs_reentry] = true
        begin
          Instrument.apply(self, sql) do |effective|
            rewritten = args.dup
            rewritten[0] = effective
            yield(rewritten)
          end
        ensure
          Thread.current[:ppcs_reentry] = false
        end
      end
    end
  end

  def self.checkpoint(name, data = {})
    Protocol.send({ 'type' => 'checkpoint', 'name' => name }.merge(data))
    msg = Protocol.read
    return msg if msg['type'] == 'resume' && msg['name'] == name
    raise ProtocolError, "expected resume for checkpoint #{name.inspect}, got #{msg.inspect}"
  end

  def self.bounded_unit(bound_ms)
    started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    value = Timeout.timeout(bound_ms / 1000.0) { yield }
    elapsed = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - started) * 1000).round
    { 'outcome' => 'completed', 'elapsed_ms' => elapsed }.merge(value)
  rescue Timeout::Error
    { 'outcome' => 'pending', 'elapsed_ms' => bound_ms }
  end

  def self.run(describe:, modes:, open:, cases:)
    $stdout.sync = true
    message = Protocol.read
    mode_id = message['mode']
    mode = modes[mode_id]
    Protocol.send(
      describe.call.merge(
        'type' => 'hello',
        'runtime' => { 'name' => 'ruby', 'version' => RUBY_VERSION },
        'mode' => mode_id,
        'configuration' => mode ? mode[:configuration] : {}
      )
    )

    impl = cases[message.dig('case', 'id')]
    unless mode
      return finish_error("unknown mode #{mode_id.inspect}")
    end
    unless impl
      Protocol.send('type' => 'result', 'status' => 'not_implemented', 'reason' => "this adapter does not implement #{message.dig('case', 'id')}")
      exit 0
    end

    opened = nil
    result = nil
    begin
      opened = open.call(message, mode)
      outcome = impl.call(opened[:context], message)
      checkpoint('after-end')
      result = { 'status' => 'completed' }.merge(outcome)
    rescue StandardError => e
      result = {
        'status' => 'error',
        'error' => err_info(e).merge('protocol' => e.is_a?(ProtocolError))
      }
    end

    diagnostics = {}
    begin
      diagnostics = opened[:diagnostics].call if opened && opened[:diagnostics]
    rescue StandardError => e
      diagnostics = { 'diagnostics_error' => e.message }
    end
    if opened && opened[:close]
      close_note = close_within(5) { opened[:close].call }
      diagnostics = diagnostics.merge('close' => close_note) if close_note
    end
    Protocol.send({ 'type' => 'result' }.merge(result).merge('diagnostics' => diagnostics))
    exit 0
  end

  def self.finish_error(text)
    Protocol.send('type' => 'result', 'status' => 'error', 'error' => { 'class' => 'AdapterError', 'code' => nil, 'message' => text, 'protocol' => false })
    exit 0
  end

  def self.close_within(seconds)
    Timeout.timeout(seconds) { yield }
    nil
  rescue Timeout::Error
    "the framework did not close within #{seconds} s"
  rescue StandardError => e
    "closing the framework failed: #{e.message}"
  end

  def self.case_tools(message)
    {
      'markers' => message['markers'],
      'settings' => message.dig('case', 'settings') || {},
      'mode' => message['mode'],
      'migration' => message['migration']
    }
  end

  class << self
    attr_accessor :last_commit
  end
end
