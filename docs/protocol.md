# Adapter protocol, version 1

An adapter is a program, in any language, that runs one catalog case with one framework's native APIs. The runner starts it once per case, and once per repetition. The two talk in newline-delimited JSON (UTF-8):

- the runner writes to the adapter's **stdin**;
- the adapter writes to its **stdout**.

A **protocol line** is a JSON object with `"ppcs": 1`. Any other stdout line, and everything on stderr, is kept as diagnostics, because libraries print. The protocol is deliberately small:

- the adapter runs the case;
- the runner observes and injects faults at checkpoints.

There is no transaction API, no RPC, and no shared library: PPCS's JavaScript adapters use `adapters/node-kit/`, but nothing requires it. `adapters/django`, `adapters/sqlalchemy`, `adapters/sqlalchemy-core`, and `adapters/tortoise` are Python implementations of this protocol. Django drives `transaction.atomic()`. SQLAlchemy drives `Session.begin()` and `Session.begin_nested()`. SQLAlchemy Core drives `Connection.begin()` and `Connection.begin_nested()` and does not use the ORM `Session`. Tortoise drives `in_transaction()`, and a nested `in_transaction()` is a savepoint. `adapters/prisma` drives `prisma.$transaction()` on `@prisma/adapter-pg`, and a nested `tx.$transaction()` is a savepoint. `adapters/spring-jdbc` is a Java implementation. It drives Spring `TransactionTemplate` on `DataSourceTransactionManager`, and writes with `JdbcTemplate`. `adapters/spring-tx` drives the same transaction manager with `PreparedStatement` on `DataSourceUtils.getConnection`, and a second mode drives `@Transactional` through `TransactionInterceptor`. The cases each one runs are listed in its `adapter.json`.

## Messages

| Direction | `type` | When | Fields |
| --- | --- | --- | --- |
| runner → adapter | `case` | First, once | `case` (`id`, `family`, `version`, `title`, `settings`), `mode`, `repetition` (1, 2, 3, …), `connection` (`host`, `port`, `user`, `password`, `database`, `application_name`), `markers` (label → value). A migration case also sends `migration`: `role`, `operation` (`apply` or `revert`), `gate`, `migrationId`, `reversal`, `hold` |
| adapter → runner | `hello` | After reading `case`, once | `adapter`, `framework`, `driver` (each `name` and `version`), `components` (name → version), `runtime` (`name`, `version`), `mode`, `configuration` (what the mode changes) |
| adapter → runner | `checkpoint` | At each checkpoint the case declares, and at `after-end` | `name`, `pid` (the backend running the current transaction), `xid` (its `pg_current_xact_id()`, as text) when the case captures it; `transaction_isolation` (its `current_setting('transaction_isolation')`, read in the same statement as `xid`) when the checkpoint declares `captures_isolation` |
| runner → adapter | `resume` | After observing a checkpoint | `name`, `actions` (what the runner did, for example `{ "action": "terminate_backend", "pid": 123, "terminated": true, "gone": true }`) |
| adapter → runner | `result` | Last, once; then exit | `status`, plus the fields below |

**`result` fields:**

| Field | Meaning |
| --- | --- |
| `status` | `completed`; `not_implemented`; or `error` (with `error`). Any other status, including `unsupported`, makes the case INCONCLUSIVE: only the manifest declares a case unsupported |
| `reported` | When completed, one of:<br>• `committed`: the API reported success;<br>• `rolled_back`: it reported a rollback;<br>• `failed`: it raised an error that asserts neither outcome;<br>• `pending`: the call had not returned when the adapter stopped waiting.<br>`pending` is never a basis for PASS or FAIL |
| `basis` | What was observed, for example `db.transaction(callback) resolved` |
| `contract` | The framework's documented or source-level contract that gives the observation its meaning. The report quotes it as the contract basis of a FAIL. |
| `api_error` | The error the API raised (`class`, `code`, `message`). Required with `rolled_back` and `failed`, which are reports of an error |
| `steps` | Observations at intermediate steps, such as the caught unique violation, or the client-side fault (`mode`, how often it `fired`, and for a rewrite PostgreSQL's `reply_codes`) |
| `form` | Where the case leaves the framework a choice of native form, the form used, and why |
| `diagnostics` | Anything else: a statement trace, warnings the framework logged. Never used for classification. |

**Example** (TX-01A, abbreviated):

```text
runner  {"ppcs":1,"type":"case","case":{"id":"TX-01A.caught-error-then-commit",...},"mode":"native","repetition":1,"connection":{...},"markers":{"tx":"tx-8f6a3c"}}
adapter {"ppcs":1,"type":"hello","adapter":{"name":"lucid","version":"0.1.0"},"framework":{"name":"@adonisjs/lucid","version":"22.4.2"},...}
adapter {"ppcs":1,"type":"checkpoint","name":"after-write","pid":5262,"xid":"1165"}
runner  {"ppcs":1,"type":"resume","name":"after-write","actions":[]}
adapter {"ppcs":1,"type":"checkpoint","name":"before-end","pid":5262}
runner  {"ppcs":1,"type":"resume","name":"before-end","actions":[]}
adapter {"ppcs":1,"type":"checkpoint","name":"after-end"}
runner  {"ppcs":1,"type":"resume","name":"after-end","actions":[]}
adapter {"ppcs":1,"type":"result","status":"completed","reported":"committed","basis":"db.transaction(callback) resolved","contract":"...","steps":{"violation":{"code":"23505"}}}
```

## Rules

- **Native APIs only.** Use the framework's ordinary, documented APIs. Do not patch the framework to change its behaviour; a mitigation is a separate execution mode, never the native one (`docs/methodology.md`).
- **The identity comes from inside the transaction.** Read `pg_current_xact_id()` and `pg_backend_pid()` through the transaction's own connection, after the transaction has written. The runner checks that the ID is that session's transaction. At a checkpoint that declares `captures_isolation` (TX-05), read `current_setting('transaction_isolation')` in the same statement, and report it as `transaction_isolation`. The runner counts it only when its own lock evidence agrees.
- **Writes are sent where the case says.** A case's `marker_writes` names the checkpoint by which each marker's write must have reached PostgreSQL. Make sure it has, for example by flushing a unit of work, unless the write is declared `possibly-pending`.
- **Checkpoints:**
  - report only those the case declares, plus `after-end`;
  - report each one once, in order: a repeated checkpoint, such as one inside a retried transaction body, is a protocol error;
  - block until the matching `resume`.
  An optional checkpoint, such as one inside a unit of work that never got a connection, may be missing.
- **`after-end` is implicit in every case.** Report it as soon as the framework's API has returned, before closing the framework. The runner records the state at report time there. `adapters/node-kit/adapter-main.mjs` sends it after the case's implementation returns.
- **`after-fault`.** A case with a client-side fault (category C) declares it. Report it from the driver layer as the fault takes effect, before the framework sees the error: after withholding the statement, or after PostgreSQL's reply to the rewritten one. `adapters/node-kit/pg-instrument.mjs` does this through the fault's `onFire` hook.
- **Mapping `reported`.** Map the API's outcome by the framework's contract, and state that contract in `contract`. For a managed transaction:
  - resolved is `committed`;
  - rejected with the callback's own error is `rolled_back` (rolling back and rethrowing is the usual contract);
  - any other rejection is `failed`.
- **Never report a protocol failure as an outcome.** If a checkpoint exchange fails, the result's status is `error`.
- **Faults:**
  - The runner injects category B faults.
  - An adapter that injects category C or D faults in its own driver layer reports each one in `steps.fault`. Its `fired` count must be exactly one.
  - Such faults are client-side injections, and must not be presented as network failures.
- **UNSUPPORTED and NOT_RUN are declared in the manifest.** List the cases the framework cannot run under `unsupported`, each with a reason and a class. A case missing from both `implements` and `unsupported` is NOT_RUN.
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
  "rollback_claim_channels": [],
  "unsupported": {
    "TX-04.independent-inner": { "class": "not-applicable-by-design", "reason": "Lucid has no propagation modes and no deferred writes: …" }
  }
}
```

- **`command`** runs in the adapter's directory, with an environment that carries no `PG*` or `PPCS_*` variables. The connection comes only in the `case` message.
- **`shared`** lists other directories whose files count toward the adapter's source digest.
- **`kind`** is one of `native`, `recommended`, `configured`, `hardened`, `control` and `fixture`. A `recommended` mode must cite the framework's documentation that recommends it, in `documentation`.
- **`cases`** on a mode limits the mode to those cases. The CTL-01 cases always run in every mode, because they gate its other results.
- **`rollback_claim_channels`** lists the channels the adapter observes through which the framework could claim a confirmed rollback: `result`, an error type, or a rollback hook or event. Without one, TX-01B.2 is recorded as not exercised (`docs/methodology.md`).
- **`unsupported`** maps a case to its `reason` and `class`: `capability-absent` (the supported API lacks what the case exercises) or `not-applicable-by-design` (the hazard cannot arise by the framework's design). A plain string is read as a `capability-absent` reason.
- **`expectations`** (control adapters only) maps each case to the classification each mode must reach, `PASS` or `FAIL`. Every run checks them, and a framework's result for a case counts only if they held.
