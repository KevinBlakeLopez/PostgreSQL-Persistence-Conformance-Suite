# Adapter protocol, version 1

An adapter is a program, in any language, that runs one catalog case with one framework's native APIs. The runner starts it once per case. The two talk in newline-delimited JSON (UTF-8):

- the runner writes to the adapter's **stdin**;
- the adapter writes to its **stdout**.

A **protocol line** is a JSON object with `"ppcs": 1`. Any other stdout line, and everything on stderr, is kept as diagnostics, because libraries print. The protocol is deliberately small:

- the adapter runs the case;
- the runner observes and injects faults at checkpoints.

There is no transaction API, no RPC, and no shared library: PPCS's JavaScript adapters use `adapters/node-kit/`, but nothing requires it.

## Messages

| Direction | `type` | When | Fields |
| --- | --- | --- | --- |
| runner → adapter | `case` | First, once | `case` (`id`, `family`, `version`, `title`, `settings`), `mode`, `connection` (`host`, `port`, `user`, `password`, `database`, `application_name`), `markers` (label → value) |
| adapter → runner | `hello` | After reading `case`, once | `adapter`, `framework`, `driver` (each `name` and `version`), `components` (name → version), `runtime` (`name`, `version`), `mode`, `configuration` (what the mode changes) |
| adapter → runner | `checkpoint` | At each checkpoint the case declares | `name`, `pid` (the backend running the current transaction), `xid` (its `pg_current_xact_id()`, as text) when the case captures it |
| runner → adapter | `resume` | After observing a checkpoint | `name`, `actions` (what the runner did, for example `{ "action": "terminate_backend", "pid": 123, "terminated": true, "gone": true }`) |
| adapter → runner | `result` | Last, once; then exit | `status`, plus the fields below |

**`result` fields:**

| Field | Meaning |
| --- | --- |
| `status` | `completed`; `unsupported` (with `reason`: the framework's supported API lacks the capability); `not_implemented`; or `error` (with `error`) |
| `reported` | When completed: `committed` (the API reported success), `rolled_back` (it reported a rollback), or `failed` (it raised an error that asserts neither outcome) |
| `basis` | What was observed, for example `db.transaction(callback) resolved` |
| `contract` | The framework's documented or source-level contract that gives the observation its meaning. The report quotes it as the contract basis of a FAIL. |
| `api_error` | The error the API raised, if any (`class`, `code`, `message`) |
| `steps` | Observations at intermediate steps, such as the caught unique violation, or how often a client-side fault fired |
| `diagnostics` | Anything else: a statement trace, warnings the framework logged. Never used for classification. |

**Example** (TX-01A, abbreviated):

```text
runner  {"ppcs":1,"type":"case","case":{"id":"TX-01A.caught-error-then-commit",...},"mode":"native","connection":{...},"markers":{"tx":"tx-8f6a3c"}}
adapter {"ppcs":1,"type":"hello","adapter":{"name":"lucid","version":"0.1.0"},"framework":{"name":"@adonisjs/lucid","version":"22.4.2"},...}
adapter {"ppcs":1,"type":"checkpoint","name":"after-write","pid":5262,"xid":"1165"}
runner  {"ppcs":1,"type":"resume","name":"after-write","actions":[]}
adapter {"ppcs":1,"type":"checkpoint","name":"before-end","pid":5262}
runner  {"ppcs":1,"type":"resume","name":"before-end","actions":[]}
adapter {"ppcs":1,"type":"result","status":"completed","reported":"committed","basis":"db.transaction(callback) resolved","contract":"...","steps":{"violation":{"code":"23505"}}}
```

## Rules

- **Native APIs only.** Use the framework's ordinary, documented APIs. Do not patch the framework to change its behaviour; a mitigation is a separate execution mode, never the native one (`docs/methodology.md`).
- **The identity comes from inside the transaction.** Read `pg_current_xact_id()` and `pg_backend_pid()` through the transaction's own connection.
- **Checkpoints:**
  - report only those the case declares;
  - report them in order;
  - block until the matching `resume`.
  An optional checkpoint, such as one inside a unit of work that never got a connection, may be missing.
- **Mapping `reported`.** Map the API's outcome by the framework's contract, and state that contract in `contract`. For a managed transaction:
  - resolved is `committed`;
  - rejected with the callback's own error is `rolled_back` (rolling back and rethrowing is the usual contract);
  - any other rejection is `failed`.
- **Never report a protocol failure as an outcome.** If a checkpoint exchange fails, the result's status is `error`.
- **Faults:**
  - The runner injects category B faults.
  - An adapter that injects category C or D faults in its own driver layer reports how often each fired (`steps.fault.fired`).
  - Such faults are client-side injections, and must not be presented as network failures.
- **UNSUPPORTED and NOT_RUN are declared in the manifest.** List the framework's missing capabilities under `unsupported`, each with a reason. A case missing from both `implements` and `unsupported` is NOT_RUN.
- **No credentials in output.** The runner removes the password from everything it records, but adapters should not print connection details in the first place.

## Bounds

The runner kills an adapter that has not finished within the case limit (60 s by default, `--timeout`). It also kills one that has not exited 10 s after its result. Either way, the case is INCONCLUSIVE, never a result.

Adapters bound their own waits, as cases specify. For example, TX-03 gives the next unit of work `bound_ms`, and the JavaScript adapters bound the framework's shutdown at 5 s.

## Manifest: `adapters/<name>/adapter.json`

```json
{
  "manifest": "ppcs-adapter/1",
  "name": "lucid",
  "framework": "@adonisjs/lucid",
  "description": "…",
  "command": ["node", "main.mjs"],
  "shared": ["../node-kit"],
  "modes": [
    { "id": "native", "kind": "native", "description": "…" },
    { "id": "pre-commit-probe", "kind": "hardened", "description": "…", "cases": ["TX-01A.caught-error-then-commit"] }
  ],
  "implements": ["CTL-01.commit", "…"],
  "unsupported": { "TX-04.independent-inner": "Lucid has no propagation modes: …" }
}
```

- **`command`** runs in the adapter's directory, with an environment that carries no `PG*` or `PPCS_*` variables. The connection comes only in the `case` message.
- **`shared`** lists other directories whose files count toward the adapter's source digest.
- **`kind`** is one of `native`, `recommended`, `configured`, `hardened`, `control` and `fixture`.
- **`cases`** on a mode limits the mode to those cases.
