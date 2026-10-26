// CHK-10: run PPCS's category-E proxy, harness/lib/pg-wire-proxy.mjs, unchanged, as a child process.
// It forwards each client to the CHK-10 server. When the server's reply through ReadyForQuery reports
// COMMIT, it does not write that reply and closes both sockets. PostgreSQL has already committed.
// stdout, line 1: {"listening": <port>}. When stdin ends: {"dropped": <count>}, then the process exits.
import { startCommitReplyProxy } from '../../../../harness/lib/pg-wire-proxy.mjs'

const CHK10_PORT = 55496
const port = Number(process.argv[2])
if (port !== CHK10_PORT) {
  process.stderr.write(`refusing port ${process.argv[2]}: only the CHK-10 server's ${CHK10_PORT}\n`)
  process.exit(2)
}
const proxy = await startCommitReplyProxy({ host: '127.0.0.1', port })
process.stdout.write(`${JSON.stringify({ listening: proxy.port })}\n`)
process.stdin.on('end', () => {
  process.stdout.write(`${JSON.stringify({ dropped: proxy.dropped() })}\n`, () => process.exit(0))
})
process.stdin.resume()
