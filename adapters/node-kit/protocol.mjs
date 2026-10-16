// The adapter side of the PPCS adapter protocol (docs/protocol.md), for adapters written in JavaScript. Adapters in
// other languages implement the same few messages themselves; nothing here is required by the runner.
//
//   runner -> adapter   {"ppcs":1,"type":"case", ...}         once, first
//   adapter -> runner   {"ppcs":1,"type":"hello", ...}        once, after reading the case
//   adapter -> runner   {"ppcs":1,"type":"checkpoint","name":..., "pid":..., "xid":...}   then wait for:
//   runner -> adapter   {"ppcs":1,"type":"resume","name":...}
//   adapter -> runner   {"ppcs":1,"type":"result", ...}       once, last; then exit
import { createInterface } from 'node:readline'

const queue = []
const waiters = []
let closed = false
createInterface({ input: process.stdin })
  .on('line', (line) => {
    let msg
    try { msg = JSON.parse(line) } catch { return }
    if (msg?.ppcs !== 1) return
    const waiter = waiters.shift()
    if (waiter) waiter.resolve(msg)
    else queue.push(msg)
  })
  .on('close', () => {
    closed = true
    for (const w of waiters.splice(0)) w.reject(new Error('the runner closed the protocol stream'))
  })

function next() {
  if (queue.length) return Promise.resolve(queue.shift())
  if (closed) return Promise.reject(new Error('the runner closed the protocol stream'))
  return new Promise((resolve, reject) => waiters.push({ resolve, reject }))
}

function send(msg) {
  return new Promise((resolve) => process.stdout.write(`${JSON.stringify({ ppcs: 1, ...msg })}\n`, resolve))
}

export async function readCase() {
  const msg = await next()
  if (msg.type !== 'case') throw new Error(`expected a case message, got "${msg.type}"`)
  return msg
}

export const hello = (info) => send({ type: 'hello', ...info })

/** Reports a checkpoint and waits until the runner has observed (and injected any fault) and says to resume. */
export async function checkpoint(name, data = {}) {
  await send({ type: 'checkpoint', name, ...data })
  const msg = await next()
  if (msg.type !== 'resume' || msg.name !== name) throw new Error(`expected resume for checkpoint "${name}", got ${JSON.stringify(msg)}`)
  return msg
}

/** Sends the result. The adapter should exit afterwards; the runner kills adapters that do not. */
export const finish = (result) => send({ type: 'result', ...result })
