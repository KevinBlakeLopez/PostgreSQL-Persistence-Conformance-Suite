// Preloaded with --import: the process may only reach 127.0.0.1:$PGPORT.
import net from 'node:net'

const PORT = Number(process.env.PGPORT)
if (!Number.isInteger(PORT) || PORT < 55000) throw new Error('net guard: PGPORT must be the run container port (55000+)')

const connect = net.Socket.prototype.connect
net.Socket.prototype.connect = function (...args) {
  const o = typeof args[0] === 'object' && args[0] !== null ? args[0] : { port: args[0], host: args[1] }
  if (o.path || Number(o.port) !== PORT || o.host !== '127.0.0.1') {
    throw new Error(`net guard: refused ${o.path ?? `${o.host}:${o.port}`}`)
  }
  return connect.apply(this, args)
}
