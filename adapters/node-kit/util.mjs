// Small helpers shared by the JavaScript adapters.
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export function errInfo(e) {
  if (!e) return null
  return { class: e.constructor?.name ?? typeof e, code: e.code ?? null, message: String(e.message ?? e).split('\n')[0].slice(0, 300) }
}

/** Settles `promise` within `ms`: { value } or { error } or { timedOut: true }. */
export async function withTimeout(promise, ms) {
  let timer
  const timeout = new Promise((resolve) => { timer = setTimeout(() => resolve({ timedOut: true }), ms) })
  try {
    return await Promise.race([Promise.resolve(promise).then((value) => ({ value }), (e) => ({ error: errInfo(e) })), timeout])
  } finally {
    clearTimeout(timer)
  }
}

/** The installed version of `pkg`, resolved from `fromDir` (a directory) and following pnpm's symlinks. */
export function packageVersion(fromDir, pkg) {
  const require = createRequire(join(realpathSync(fromDir), 'noop.js'))
  try {
    return JSON.parse(readFileSync(require.resolve(`${pkg}/package.json`), 'utf8')).version
  } catch {
    // Packages whose "exports" hide package.json: walk up from the entry point.
    let dir = dirname(require.resolve(pkg))
    while (dir !== dirname(dir)) {
      try {
        const meta = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'))
        if (meta.name === pkg) return meta.version
      } catch { /* keep walking */ }
      dir = dirname(dir)
    }
    return 'UNKNOWN'
  }
}

/** The directory of an installed package, following pnpm's symlinks, so its own dependencies can be resolved. */
export function packageDir(fromDir, pkg) {
  const require = createRequire(join(realpathSync(fromDir), 'noop.js'))
  try {
    return dirname(realpathSync(require.resolve(`${pkg}/package.json`)))
  } catch {
    let dir = dirname(realpathSync(require.resolve(pkg)))
    while (dir !== dirname(dir)) {
      try { if (JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8')).name === pkg) return dir } catch { /* keep walking */ }
      dir = dirname(dir)
    }
    return null
  }
}
