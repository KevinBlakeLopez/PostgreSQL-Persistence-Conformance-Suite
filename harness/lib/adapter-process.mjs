// Runs one adapter process for one case, speaking the PPCS adapter protocol (docs/protocol.md): newline-delimited JSON
// on stdin and stdout. Protocol lines carry "ppcs": 1. Any other stdout line, and all of stderr, is kept as
// diagnostics, because libraries print to stdout.
//
// The runner sends one `case` message. The adapter answers `hello`, then zero or more `checkpoint` messages (each
// waits for a `resume`), then one `result`, and exits. A hard timeout bounds the whole exchange: an adapter that
// hangs is killed, and the case is recorded as INCONCLUSIVE, never as a result.
import { spawn } from 'node:child_process'
import { createInterface } from 'node:readline'

export const PROTOCOL = 1
const STDERR_LIMIT = 64 * 1024
const STDOUT_LINES_LIMIT = 200

export function runAdapter({ command, cwd, message, onCheckpoint, timeoutMs = 60000, exitGraceMs = 10000, redact = [] }) {
  const scrub = (text) => redact.filter(Boolean).reduce((t, secret) => t.split(secret).join('[redacted]'), String(text))
  // The adapter receives its connection details in the case message, never through the environment.
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith('PPCS_') && !k.startsWith('PG')))
  const started = Date.now()
  const child = spawn(command[0], command.slice(1), { cwd, env, stdio: ['pipe', 'pipe', 'pipe'] })

  const record = { hello: null, checkpoints: [], result: null, protocolErrors: [], stdout: [], stderr: '', exit: null, timedOut: false, durationMs: null }
  const send = (msg) => { if (child.stdin.writable) child.stdin.write(`${JSON.stringify({ ppcs: PROTOCOL, ...msg })}\n`) }
  child.stdin.on('error', () => {}) // the adapter may exit before reading everything

  child.stderr.on('data', (d) => { record.stderr = (record.stderr + scrub(d)).slice(-STDERR_LIMIT) })

  let pending = Promise.resolve() // checkpoints are handled one at a time, in order
  createInterface({ input: child.stdout }).on('line', (raw) => {
    const line = scrub(raw) // protocol messages too: an error message the adapter reports could contain the password
    let msg = null
    try { msg = JSON.parse(line) } catch { /* not a protocol line */ }
    if (!msg || typeof msg !== 'object' || msg.ppcs !== PROTOCOL) {
      if (record.stdout.length < STDOUT_LINES_LIMIT) record.stdout.push(scrub(line).slice(0, 500))
      return
    }
    if (msg.type === 'hello') {
      if (record.hello) record.protocolErrors.push('a second hello message')
      record.hello = msg
    } else if (msg.type === 'checkpoint') {
      if (!record.hello) record.protocolErrors.push(`checkpoint "${msg.name}" before hello`)
      const entry = { name: msg.name, reported: msg, at_ms: Date.now() - started }
      record.checkpoints.push(entry)
      pending = pending.then(async () => {
        try {
          entry.runner = await onCheckpoint(msg)
        } catch (e) {
          entry.runner = { error: String(e?.message ?? e) }
          record.protocolErrors.push(`runner failed at checkpoint "${msg.name}": ${entry.runner.error}`)
        }
        send({ type: 'resume', name: msg.name, actions: entry.runner?.actions ?? [] })
      })
    } else if (msg.type === 'result') {
      if (record.result) record.protocolErrors.push('a second result message')
      record.result = msg
    } else {
      record.protocolErrors.push(`unknown message type "${msg.type}"`)
    }
  })

  return new Promise((resolve) => {
    let finished = false
    const killer = setTimeout(() => { record.timedOut = true; child.kill('SIGKILL') }, timeoutMs)
    let graceTimer = null
    const watchResult = setInterval(() => {
      // After its result, an adapter has exitGraceMs to close its pools and exit.
      if (record.result && !graceTimer) graceTimer = setTimeout(() => { record.protocolErrors.push(`no exit within ${exitGraceMs} ms of the result`); child.kill('SIGKILL') }, exitGraceMs)
    }, 50)
    child.on('error', (e) => { record.protocolErrors.push(`could not start the adapter: ${e.message}`) })
    child.on('close', async (code, signal) => {
      if (finished) return
      finished = true
      clearTimeout(killer)
      clearTimeout(graceTimer)
      clearInterval(watchResult)
      await pending
      record.exit = { code, signal }
      record.durationMs = Date.now() - started
      resolve(record)
    })
    send({ type: 'case', ...message })
  })
}
