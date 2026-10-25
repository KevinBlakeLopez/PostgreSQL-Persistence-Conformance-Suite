// A cleartext PostgreSQL wire recorder for this study.
//
// It forwards every byte unchanged in both directions. From a copy of each stream it reports, per client
// connection, what the client sent (startup, simple queries, Parse, Bind, Execute, Close, Sync, Terminate)
// and what the server answered (CommandComplete tags, ErrorResponse SQLSTATEs, ReadyForQuery status,
// BackendKeyData). It never drops, delays, or rewrites a message. That is the difference from
// harness/lib/pg-wire-proxy.mjs, which drops one COMMIT reply.
//
// Authentication messages are reported by type only, never by content.
//
// The client should not negotiate encryption (sslmode=disable, gssencmode=disable). If the server
// accepts TLS or GSS encryption, the connection is still forwarded, and recording stops for it.
import net from 'node:net'

const SSL_REQUEST = 80877103
const GSSENC_REQUEST = 80877104
const CANCEL_REQUEST = 80877102

function cstring(buf, offset) {
  const end = buf.indexOf(0, offset)
  return [buf.toString('utf8', offset, end), end + 1]
}

// Splits one direction of a connection into messages. Every server message has a type byte. The client's
// first messages do not: its startup packet and its SSL or GSS encryption requests, so the client side
// starts untyped and becomes typed after the startup packet. The server answers an encryption request with
// one bare byte, which `expectByte()` arranges to read.
class Framer {
  constructor(typed, onMessage, onByte) {
    this.buf = Buffer.alloc(0)
    this.typed = typed
    this.stopped = false
    this.pendingBytes = 0
    this.onMessage = onMessage
    this.onByte = onByte
  }

  expectByte() {
    this.pendingBytes++
  }

  push(chunk) {
    if (this.stopped) return
    this.buf = Buffer.concat([this.buf, chunk])
    for (;;) {
      if (this.stopped) return
      if (this.pendingBytes > 0) {
        if (this.buf.length < 1) return
        const byte = String.fromCharCode(this.buf[0])
        this.buf = this.buf.subarray(1)
        this.pendingBytes--
        this.onByte(byte)
        continue
      }
      const head = this.typed ? 5 : 4
      if (this.buf.length < head) return
      const length = this.buf.readInt32BE(this.typed ? 1 : 0)
      const total = this.typed ? length + 1 : length
      if (this.buf.length < total) return
      const type = this.typed ? String.fromCharCode(this.buf[0]) : null
      const body = this.buf.subarray(head, total)
      this.buf = this.buf.subarray(total)
      this.onMessage(type, body)
    }
  }
}

function frontendMessage(type, body, emit, framer, backend) {
  if (type === null) {
    const code = body.readInt32BE(0)
    if (code === SSL_REQUEST || code === GSSENC_REQUEST) {
      emit({ msg: code === SSL_REQUEST ? 'SSLRequest' : 'GSSENCRequest' })
      backend.expectByte()
      return
    }
    if (code === CANCEL_REQUEST) {
      emit({ msg: 'CancelRequest' })
      framer.stopped = true
      return
    }
    // StartupMessage: the protocol version, then name/value pairs.
    const params = {}
    let offset = 4
    while (offset < body.length && body[offset] !== 0) {
      const [name, next] = cstring(body, offset)
      const [value, after] = cstring(body, next)
      params[name] = value
      offset = after
    }
    emit({
      msg: 'Startup',
      protocol: `${code >> 16}.${code & 0xffff}`,
      database: params.database ?? null,
      application_name: params.application_name ?? null,
    })
    framer.typed = true
    return
  }
  switch (type) {
    case 'Q':
      emit({ msg: 'Query', sql: cstring(body, 0)[0] })
      break
    case 'P': {
      const [name, next] = cstring(body, 0)
      emit({ msg: 'Parse', name, sql: cstring(body, next)[0] })
      break
    }
    case 'B': {
      const [, next] = cstring(body, 0)
      emit({ msg: 'Bind', statement: cstring(body, next)[0] })
      break
    }
    case 'E':
      emit({ msg: 'Execute' })
      break
    case 'C':
      emit({ msg: 'Close', target: String.fromCharCode(body[0]), name: cstring(body, 1)[0] })
      break
    case 'D':
      emit({ msg: 'Describe' })
      break
    case 'S':
      emit({ msg: 'Sync' })
      break
    case 'H':
      emit({ msg: 'Flush' })
      break
    case 'X':
      emit({ msg: 'Terminate' })
      break
    case 'p':
      emit({ msg: 'AuthenticationResponse' })
      break
    default:
      emit({ msg: `frontend ${type}` })
  }
}

function errorFields(body) {
  const fields = {}
  let offset = 0
  while (offset < body.length && body[offset] !== 0) {
    const code = String.fromCharCode(body[offset])
    const [value, next] = cstring(body, offset + 1)
    fields[code] = value
    offset = next
  }
  return fields
}

const BACKEND_NAMES = {
  1: 'ParseComplete',
  2: 'BindComplete',
  3: 'CloseComplete',
  n: 'NoData',
  t: 'ParameterDescription',
  T: 'RowDescription',
  I: 'EmptyQueryResponse',
  s: 'PortalSuspended',
}

function backendMessage(type, body, emit) {
  switch (type) {
    case 'C':
      emit({ msg: 'CommandComplete', tag: cstring(body, 0)[0] })
      break
    case 'E':
    case 'N': {
      const fields = errorFields(body)
      emit({ msg: type === 'E' ? 'ErrorResponse' : 'NoticeResponse', sqlstate: fields.C ?? null, message: fields.M ?? null })
      break
    }
    case 'Z':
      emit({ msg: 'ReadyForQuery', status: String.fromCharCode(body[0]) })
      break
    case 'K':
      emit({ msg: 'BackendKeyData', pid: body.readInt32BE(0) })
      break
    case 'R':
      emit({ msg: 'Authentication', code: body.readInt32BE(0) })
      break
    case 'D':
    case 'S':
      // DataRow and ParameterStatus: not needed for this study.
      break
    default:
      emit({ msg: BACKEND_NAMES[type] ?? `backend ${type}` })
  }
}

/**
 * Listens on an ephemeral port of 127.0.0.1 and forwards each connection to the server.
 * `onEvent` receives { conn, seq, at_ms, dir, msg, ... }. `dir` is F (client to server) or B (server
 * to client), as in libpq's trace output.
 */
export function startRecorder({ host, port, onEvent }) {
  const started = performance.now()
  let connections = 0
  let seq = 0
  const sockets = new Set()

  const server = net.createServer((client) => {
    const conn = ++connections
    const emitFor = (dir) => (event) => onEvent({ conn, seq: ++seq, at_ms: Math.round((performance.now() - started) * 1000) / 1000, dir, ...event })
    const emitF = emitFor('F')
    const emitB = emitFor('B')
    const upstream = net.connect(port, host)
    sockets.add(client)
    sockets.add(upstream)

    const backend = new Framer(
      true,
      (type, body) => backendMessage(type, body, emitB),
      (byte) => {
        emitB({ msg: 'EncryptionResponse', byte })
        if (byte !== 'N') {
          frontend.stopped = true
          backend.stopped = true
          emitB({ msg: 'encrypted: recording stopped' })
        }
      },
    )
    const frontend = new Framer(false, (type, body) => frontendMessage(type, body, emitF, frontend, backend), () => {})

    // Parse before forwarding, so an encryption request is known before its one-byte answer can arrive.
    client.on('data', (chunk) => {
      frontend.push(chunk)
      upstream.write(chunk)
    })
    upstream.on('data', (chunk) => {
      backend.push(chunk)
      client.write(chunk)
    })
    const close = () => {
      client.destroy()
      upstream.destroy()
      sockets.delete(client)
      sockets.delete(upstream)
    }
    client.on('close', close)
    upstream.on('close', close)
    client.on('error', close)
    upstream.on('error', close)
  })

  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      resolve({
        port: server.address().port,
        close: () =>
          new Promise((done) => {
            for (const socket of sockets) socket.destroy()
            server.close(() => done())
          }),
      })
    })
  })
}
