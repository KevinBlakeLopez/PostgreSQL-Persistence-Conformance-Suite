// A cleartext PostgreSQL wire proxy that drops the reply to one COMMIT.
//
// The client speaks to this process. This process speaks to the real server. Startup and authentication are
// forwarded. When the server's reply contains CommandComplete for COMMIT, the proxy does not write that
// reply to the client and closes the client socket. The server has already committed. The client never
// parsed the reply. Replies to earlier commands, including a Parse of COMMIT, are forwarded: a driver that
// waits for ParseComplete before Execute would otherwise stall before the commit.
//
// An SSL request is answered by the real server. If the server accepts SSL, the rest of the connection is
// an opaque byte pipe and no reply is dropped: the proxy only understands cleartext.
import net from 'node:net'

const SSL_REQUEST = 80877103
// These Authentication codes ask the client for a password or SASL response. AuthenticationSASLFinal (12)
// does not: the server follows it with AuthenticationOk on its own.
const CLIENT_AUTH = new Set([3, 5, 10, 11])

class Reader {
  constructor(socket) {
    this.buf = Buffer.alloc(0)
    this.wait = null
    this.ended = false
    socket.on('data', (chunk) => {
      this.buf = Buffer.concat([this.buf, chunk])
      this.flush()
    })
    const end = () => { this.ended = true; this.flush() }
    socket.on('end', end)
    socket.on('close', end)
  }

  flush() {
    if (!this.wait) return
    if (this.buf.length >= this.wait.n) {
      const out = Buffer.from(this.buf.subarray(0, this.wait.n))
      this.buf = this.buf.subarray(this.wait.n)
      const { resolve } = this.wait
      this.wait = null
      resolve(out)
      return
    }
    if (this.ended) {
      const { reject } = this.wait
      this.wait = null
      reject(new Error('the socket closed'))
    }
  }

  read(n) {
    return new Promise((resolve, reject) => {
      this.wait = { n, resolve, reject }
      this.flush()
    })
  }
}

async function readMessage(reader) {
  const type = await reader.read(1)
  const lenBuf = await reader.read(4)
  const len = lenBuf.readInt32BE(0)
  if (len < 4) throw new Error(`bad message length ${len}`)
  const payload = await reader.read(len - 4)
  return { type: type[0], raw: Buffer.concat([type, lenBuf, payload]), payload }
}

async function readUntilReady(reader) {
  const parts = []
  for (;;) {
    const message = await readMessage(reader)
    parts.push(message.raw)
    if (message.type === 0x5a) return Buffer.concat(parts) // ReadyForQuery
  }
}

/** True when the server's reply through ReadyForQuery includes CommandComplete for COMMIT. */
function responseCommits(buf) {
  let offset = 0
  while (offset + 5 <= buf.length) {
    const type = buf[offset]
    const len = buf.readInt32BE(offset + 1)
    if (len < 4 || offset + 1 + len > buf.length) return false
    if (type === 0x43) {
      const tag = buf.toString('utf8', offset + 5, offset + 1 + len - 1)
      if (tag === 'COMMIT') return true
    }
    offset += 1 + len
  }
  return false
}

/** What the server will answer for this extended-protocol message, once the client flushes or syncs. */
function expectKind(message) {
  const t = message.type
  if (t === 0x50) return 'parse'
  if (t === 0x42) return 'bind'
  if (t === 0x45) return 'execute'
  if (t === 0x43) return 'close'
  if (t === 0x44) return message.payload[0] === 0x53 ? 'describe-statement' : 'describe-portal'
  return null
}

/**
 * How `type` relates to the reply still owed for `kind`.
 * `more` means this message belongs to the reply and another message finishes it
 * (ParameterDescription before NoData, DataRow before CommandComplete).
 */
function stepFor(kind, type) {
  if (type === 0x4e) return 'skip' // NoticeResponse
  if (type === 0x45) return 'error'
  if (kind === 'parse' && type === 0x31) return 'done'
  if (kind === 'bind' && type === 0x32) return 'done'
  if (kind === 'close' && type === 0x33) return 'done'
  if (kind === 'describe-statement' && type === 0x74) return 'more'
  if ((kind === 'describe-statement' || kind === 'describe-portal') && (type === 0x54 || type === 0x6e)) return 'done'
  if (kind === 'execute' && (type === 0x54 || type === 0x44)) return 'more'
  if (kind === 'execute' && (type === 0x43 || type === 0x49 || type === 0x73)) return 'done'
  return 'bad'
}

/** Read the replies owed for `pending`, and ReadyForQuery when `sync` is set. */
async function readPending(reader, pending, sync) {
  const parts = []
  let index = 0
  while (index < pending.length) {
    const message = await readMessage(reader)
    parts.push(message.raw)
    const step = stepFor(pending[index], message.type)
    if (step === 'skip' || step === 'more') continue
    if (step === 'done') { index += 1; continue }
    if (step === 'error') {
      if (sync) parts.push(await readUntilReady(reader))
      return Buffer.concat(parts)
    }
    throw new Error(`unexpected server message ${message.type} for ${pending[index]}`)
  }
  if (sync) parts.push(await readUntilReady(reader))
  return Buffer.concat(parts)
}

async function forwardStartup(client, upstream) {
  const head = await client.read(8)
  const len = head.readInt32BE(0)
  const code = head.readInt32BE(4)
  if (len === 8 && code === SSL_REQUEST) {
    upstream.socket.write(head)
    const answer = await upstream.read(1)
    client.socket.write(answer)
    if (answer[0] === 0x53) return 'ssl'
    const startupLenBuf = await client.read(4)
    const startupLen = startupLenBuf.readInt32BE(0)
    const rest = await client.read(startupLen - 4)
    upstream.socket.write(Buffer.concat([startupLenBuf, rest]))
    return 'clear'
  }
  const rest = await client.read(len - 8)
  upstream.socket.write(Buffer.concat([head, rest]))
  return 'clear'
}

async function session(clientSocket, upstreamSocket, onDrop) {
  const client = new Reader(clientSocket)
  client.socket = clientSocket
  const upstream = new Reader(upstreamSocket)
  upstream.socket = upstreamSocket
  const mode = await forwardStartup(client, upstream)
  if (mode === 'ssl') {
    clientSocket.pipe(upstreamSocket)
    upstreamSocket.pipe(clientSocket)
    return
  }
  // Authentication can take several client replies (cleartext, MD5, SCRAM) before ReadyForQuery.
  for (;;) {
    const message = await readMessage(upstream)
    clientSocket.write(message.raw)
    if (message.type === 0x5a) break
    if (message.type === 0x52 && CLIENT_AUTH.has(message.payload.readInt32BE(0))) {
      upstreamSocket.write((await readMessage(client)).raw)
    }
  }
  // Extended-protocol commands do not produce a client-visible reply until Flush or Sync.
  // asyncpg sends Parse and Describe, then Flush, and waits for ParseComplete before Bind.
  // The COMMIT reply is the later Bind/Execute/Sync result, whose CommandComplete tag is COMMIT.
  const pending = []
  for (;;) {
    const message = await readMessage(client)
    const kind = expectKind(message)
    if (kind) pending.push(kind)
    upstreamSocket.write(message.raw)
    if (message.type === 0x58) return // Terminate
    const sync = message.type === 0x53
    const flush = message.type === 0x48
    const query = message.type === 0x51
    if (!sync && !flush && !query) continue
    const queued = pending.splice(0)
    const response = query ? await readUntilReady(upstream) : await readPending(upstream, queued, sync)
    if (responseCommits(response)) {
      onDrop()
      clientSocket.destroy()
      upstreamSocket.destroy()
      return
    }
    if (response.length) clientSocket.write(response)
  }
}

/** Listen on 127.0.0.1 and forward each client to `host:port`, dropping one COMMIT reply per connection. */
export function startCommitReplyProxy({ host, port }) {
  let dropped = 0
  const server = net.createServer((client) => {
    const upstream = net.connect({ host, port })
    const fail = () => { client.destroy(); upstream.destroy() }
    client.setNoDelay(true)
    upstream.setNoDelay(true)
    client.on('error', fail)
    upstream.on('error', fail)
    upstream.on('connect', () => {
      session(client, upstream, () => { dropped += 1 }).catch(fail)
    })
  })
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      resolve({
        port: address.port,
        dropped: () => dropped,
        close: () => new Promise((done) => server.close(() => done())),
      })
    })
  })
}
