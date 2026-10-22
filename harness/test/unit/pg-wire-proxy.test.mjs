// The proxy drops the server's reply to COMMIT and closes the client. A query before that COMMIT is forwarded.
import net from 'node:net'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { startCommitReplyProxy } from '../../lib/pg-wire-proxy.mjs'

const listen = () => new Promise((resolve) => {
  const server = net.createServer()
  server.listen(0, '127.0.0.1', () => resolve(server))
})

const startup = () => {
  const body = Buffer.from('user\0u\0database\0d\0\0')
  const version = Buffer.alloc(4)
  version.writeInt32BE(196608)
  const len = Buffer.alloc(4)
  len.writeInt32BE(8 + body.length)
  return Buffer.concat([len, version, body])
}

const ready = (status = 0x49) => {
  const z = Buffer.alloc(6)
  z[0] = 0x5a
  z.writeInt32BE(5, 1)
  z[5] = status
  return z
}

const authOk = () => {
  const r = Buffer.alloc(9)
  r[0] = 0x52
  r.writeInt32BE(8, 1)
  r.writeInt32BE(0, 5)
  return Buffer.concat([r, ready()])
}

const query = (sql) => {
  const payload = Buffer.from(`${sql}\0`)
  const len = Buffer.alloc(4)
  len.writeInt32BE(4 + payload.length)
  return Buffer.concat([Buffer.from('Q'), len, payload])
}

const commandComplete = (tag) => {
  const payload = Buffer.from(`${tag}\0`)
  const len = Buffer.alloc(4)
  len.writeInt32BE(4 + payload.length)
  return Buffer.concat([Buffer.from('C'), len, payload])
}

const once = (socket, event) => new Promise((resolve, reject) => {
  socket.once(event, resolve)
  socket.once('error', reject)
})

const auth = (code, extra = Buffer.alloc(0)) => {
  const payload = Buffer.alloc(4 + extra.length)
  payload.writeInt32BE(code, 0)
  extra.copy(payload, 4)
  const len = Buffer.alloc(4)
  len.writeInt32BE(4 + payload.length)
  return Buffer.concat([Buffer.from('R'), len, payload])
}

const password = (text) => {
  const payload = Buffer.from(`${text}\0`)
  const len = Buffer.alloc(4)
  len.writeInt32BE(4 + payload.length)
  return Buffer.concat([Buffer.from('p'), len, payload])
}

const message = (type, payload) => {
  const len = Buffer.alloc(4)
  len.writeInt32BE(4 + payload.length)
  return Buffer.concat([Buffer.from([type]), len, payload])
}

const parse = (sql) => message(0x50, Buffer.concat([
  Buffer.from('\0'),
  Buffer.from(`${sql}\0`),
  Buffer.from([0, 0]),
]))

const bind = () => message(0x42, Buffer.concat([
  Buffer.from('\0\0'),
  Buffer.from([0, 0]),
  Buffer.from([0, 0]),
  Buffer.from([0, 0]),
]))

const execute = () => message(0x45, Buffer.concat([Buffer.from('\0'), Buffer.alloc(4)]))

const sync = () => message(0x53, Buffer.alloc(0))

const fixed = (type) => {
  const buf = Buffer.alloc(5)
  buf[0] = type
  buf.writeInt32BE(4, 1)
  return buf
}

test('a COMMIT reply is not delivered to the client', async () => {
  const seen = []
  const backend = await listen()
  backend.on('connection', (socket) => {
    socket.once('data', () => {
      socket.write(authOk())
      socket.on('data', (chunk) => {
        seen.push(chunk.toString('utf8'))
        if (chunk.includes('SELECT')) socket.write(Buffer.concat([commandComplete('SELECT 1'), ready()]))
        if (chunk.includes('COMMIT')) socket.write(Buffer.concat([commandComplete('COMMIT'), ready()]))
      })
    })
  })
  const proxy = await startCommitReplyProxy({ host: '127.0.0.1', port: backend.address().port })
  const client = net.connect(proxy.port, '127.0.0.1')
  await once(client, 'connect')
  const received = []
  client.on('data', (chunk) => received.push(Buffer.from(chunk)))
  client.write(startup())
  await new Promise((resolve) => client.once('data', resolve))
  client.write(query('SELECT 1'))
  await new Promise((resolve) => client.once('data', resolve))
  client.write(query('COMMIT'))
  await once(client, 'close')
  const bytes = Buffer.concat(received).toString('utf8')
  assert.match(bytes, /SELECT 1/)
  assert.doesNotMatch(bytes, /COMMIT/)
  assert.equal(proxy.dropped(), 1)
  assert.ok(seen.some((chunk) => chunk.includes('COMMIT')))
  client.destroy()
  await proxy.close()
  await new Promise((resolve) => backend.close(resolve))
})

test('AuthenticationSASLFinal is forwarded without another client message', async () => {
  const backend = await listen()
  backend.on('connection', (socket) => {
    let stage = 0
    socket.on('data', (chunk) => {
      if (stage === 0) {
        stage = 1
        socket.write(auth(10, Buffer.from('SCRAM-SHA-256\0\0')))
        return
      }
      if (stage === 1 && chunk[0] === 0x70) {
        stage = 2
        socket.write(auth(11, Buffer.from('r=x,s=eHh4,i=4096')))
        return
      }
      if (stage === 2 && chunk[0] === 0x70) {
        stage = 3
        socket.write(Buffer.concat([auth(12, Buffer.from('v=eHh4')), auth(0), ready()]))
        return
      }
      if (chunk.includes('COMMIT')) socket.write(Buffer.concat([commandComplete('COMMIT'), ready()]))
    })
  })
  const proxy = await startCommitReplyProxy({ host: '127.0.0.1', port: backend.address().port })
  const client = net.connect(proxy.port, '127.0.0.1')
  await once(client, 'connect')
  const received = []
  let replies = 0
  let sentCommit = false
  client.on('data', (chunk) => {
    received.push(Buffer.from(chunk))
    if (replies < 2) {
      replies += 1
      client.write(password('x'))
      return
    }
    if (!sentCommit && Buffer.concat(received).includes(0x5a)) {
      sentCommit = true
      client.write(query('COMMIT'))
    }
  })
  client.write(startup())
  await Promise.race([
    once(client, 'close'),
    new Promise((_, reject) => setTimeout(() => reject(new Error('timed out waiting for the dropped COMMIT')), 1000)),
  ])
  assert.equal(sentCommit, true)
  assert.doesNotMatch(Buffer.concat(received).toString('utf8'), /COMMIT/)
  assert.equal(proxy.dropped(), 1)
  client.destroy()
  await proxy.close()
  await new Promise((resolve) => backend.close(resolve))
})

test('an extended-protocol COMMIT reply is not delivered', async () => {
  const seen = []
  const backend = await listen()
  backend.on('connection', (socket) => {
    socket.once('data', () => {
      socket.write(authOk())
      socket.on('data', (chunk) => {
        seen.push(chunk.toString('utf8'))
        if (!chunk.includes('COMMIT')) return
        socket.write(Buffer.concat([fixed(0x31), fixed(0x32), commandComplete('COMMIT'), ready()]))
      })
    })
  })
  const proxy = await startCommitReplyProxy({ host: '127.0.0.1', port: backend.address().port })
  const client = net.connect(proxy.port, '127.0.0.1')
  await once(client, 'connect')
  const received = []
  client.on('data', (chunk) => received.push(Buffer.from(chunk)))
  client.write(startup())
  await new Promise((resolve) => client.once('data', resolve))
  client.write(Buffer.concat([parse('COMMIT'), bind(), execute(), sync()]))
  await once(client, 'close')
  assert.doesNotMatch(Buffer.concat(received).toString('utf8'), /COMMIT/)
  assert.equal(proxy.dropped(), 1)
  assert.ok(seen.some((chunk) => chunk.includes('COMMIT')))
  client.destroy()
  await proxy.close()
  await new Promise((resolve) => backend.close(resolve))
})

const describeStatement = () => message(0x44, Buffer.from('S\0'))
const flush = () => message(0x48, Buffer.alloc(0))
const parameterDescription = () => message(0x74, Buffer.from([0, 0]))

test('a driver that waits for ParseComplete still loses the COMMIT reply', async () => {
  const backend = await listen()
  let stage = 0
  backend.on('connection', (socket) => {
    socket.once('data', () => {
      socket.write(authOk())
      socket.on('data', (chunk) => {
        if (stage === 0 && chunk.includes(0x48)) {
          stage = 1
          socket.write(Buffer.concat([fixed(0x31), parameterDescription(), fixed(0x6e)]))
          return
        }
        if (stage === 1 && chunk.includes(0x53)) {
          stage = 2
          socket.write(Buffer.concat([fixed(0x32), commandComplete('COMMIT'), ready()]))
        }
      })
    })
  })
  const proxy = await startCommitReplyProxy({ host: '127.0.0.1', port: backend.address().port })
  const client = net.connect(proxy.port, '127.0.0.1')
  client.on('error', () => {})
  try {
    await once(client, 'connect')
    const received = []
    client.on('data', (chunk) => received.push(Buffer.from(chunk)))
    client.write(startup())
    await new Promise((resolve) => client.once('data', resolve))
    const afterAuth = Buffer.concat(received).length
    client.write(Buffer.concat([parse('COMMIT'), describeStatement(), flush()]))
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('timed out waiting for ParseComplete')), 1000)
      const check = () => {
        if (!Buffer.concat(received).subarray(afterAuth).includes(0x31)) return
        clearTimeout(timer)
        client.off('data', check)
        resolve()
      }
      client.on('data', check)
      check()
    })
    client.write(Buffer.concat([bind(), execute(), sync()]))
    await Promise.race([
      once(client, 'close'),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timed out waiting for the dropped COMMIT')), 1000)),
    ])
    assert.doesNotMatch(Buffer.concat(received).toString('utf8'), /COMMIT/)
    assert.equal(proxy.dropped(), 1)
    assert.equal(stage, 2)
  } finally {
    client.destroy()
    await proxy.close()
    await new Promise((resolve) => backend.close(resolve))
  }
})
