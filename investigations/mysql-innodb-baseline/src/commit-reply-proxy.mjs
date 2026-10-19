// Forwards the MySQL client protocol. When armed, the next COMMIT query is still
// forwarded, and the server packet that answers it is not written to the client.
// The client socket is closed after that packet has been read from the server.
// The server has already finished COMMIT by the time it sends that packet.

import { createServer, connect as netConnect } from 'node:net'

const COM_QUERY = 0x03

export function startCommitReplyProxy({ host, port }) {
  let armed = false
  const drops = []
  const server = createServer((clientSocket) => {
    const upstream = netConnect({ host, port })
    let upstreamReady = false
    const pendingClient = []
    let dropResponse = false

    const clientFramer = createFramer((packet) => {
      if (!armed) return
      const payload = packet.subarray(4)
      if (payload[0] !== COM_QUERY) return
      // mysql2 sends parameter_count and parameter_set_count before the SQL when
      // CLIENT_QUERY_ATTRIBUTES was negotiated. Those bytes are 0x00 0x01.
      const sql = payload.subarray(1).toString('utf8').replace(/^[\u0000-\u001f]+/, '').trim()
      if (!/^commit\s*;?$/i.test(sql)) return
      armed = false
      dropResponse = true
    })
    const serverFramer = createFramer((packet) => {
      if (!dropResponse) return false
      dropResponse = false
      const payload = packet.subarray(4)
      const first = payload[0]
      drops.push({
        payload_length: payload.length,
        first_byte: first,
        looks_like_ok: first === 0x00,
        looks_like_err: first === 0xff,
        hex_prefix: payload.subarray(0, 16).toString('hex'),
      })
      clientSocket.destroy()
      upstream.destroy()
      return true
    })

    upstream.on('connect', () => {
      upstreamReady = true
      for (const chunk of pendingClient) upstream.write(chunk)
      pendingClient.length = 0
    })
    clientSocket.on('data', (chunk) => {
      clientFramer.push(chunk)
      if (upstreamReady) upstream.write(chunk)
      else pendingClient.push(chunk)
    })
    upstream.on('data', (chunk) => {
      const forward = serverFramer.push(chunk)
      if (forward.length && clientSocket.writable) clientSocket.write(Buffer.concat(forward))
    })
    clientSocket.on('error', () => upstream.destroy())
    upstream.on('error', () => clientSocket.destroy())
    clientSocket.on('close', () => upstream.destroy())
    upstream.on('close', () => clientSocket.destroy())
  })

  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      resolve({
        port: server.address().port,
        arm() { armed = true },
        drops,
        close() { return new Promise((done) => server.close(() => done())) },
      })
    })
  })
}

function createFramer(onPacket) {
  let buffer = Buffer.alloc(0)
  return {
    push(chunk) {
      buffer = buffer.length === 0 ? Buffer.from(chunk) : Buffer.concat([buffer, chunk])
      const forward = []
      while (buffer.length >= 4) {
        const length = buffer[0] | (buffer[1] << 8) | (buffer[2] << 16)
        const total = length + 4
        if (buffer.length < total) break
        const packet = buffer.subarray(0, total)
        buffer = buffer.subarray(total)
        const dropped = onPacket(packet) === true
        if (!dropped) forward.push(Buffer.from(packet))
      }
      return forward
    },
  }
}
