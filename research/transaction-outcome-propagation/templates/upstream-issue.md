# Upstream issue template

Template. Do not file this file. Fill it from a propagation run, and get approval of the exact text before posting. Drafts in this repository stay drafts until that approval.

## 1. Library and driver versions

- Library:
- Library version:
- Driver:
- Driver version:
- Driver git revision, when the package records one:
- Runtime:
- PostgreSQL version:
- Server image digest:
- Propagation run id:

## 2. Minimal reproduction

Describe the ordinary API call. State the SQL that the application means to run, including the caught statement error and the later COMMIT or the framework call that sends it.

Keep the reproduction free of suite harness internals. A fresh database, one transaction, and a second connection for the check are enough.

## 3. Expected behavior

State the behavior the project's own documentation or source contract describes. Quote the contract. If the documentation does not promise a durable commit, say that, and say what the application can observe instead.

## 4. Actual application-visible behavior

- Reported result: `REPORTED_SUCCESS`, `REPORTED_FAILURE`, `REPORTED_ROLLBACK`, `REPORTED_UNKNOWN`, or `NO_RESULT`
- The call that returned or threw:
- Callbacks or public flags that ran:
- Basis, in one or two sentences:

## 5. Actual PostgreSQL outcome

From a second connection, not from the library's return value:

- `pg_xact_status()`:
- Marker visible:
- Transaction id:
- Session state after the call, when it was still available:

## 6. Driver-level evidence

- Command tag value:
- How it was observed: public return value, or diagnostic wrapper
- Observation class: `OBSERVED`, `INFERRED`, `NOT_OBSERVED`, `NOT_EXPOSED`, or `NOT_APPLICABLE`
- SQLSTATE of the caught statement error:
- Transaction status, when the driver exposes it:
- What was not observed:

If the command tag is inferred from a driver field, say which field and which parser, and say that the packet was not captured.

## 7. Framework source-code analysis

- Version and, when recorded, git revision:
- Function and file:
- The operation that keeps, drops, or rewrites the driver result:
- Classification of that path: documented behavior, undocumented omission, likely defect, or contract disagreement
- This template does not itself decide that the path is a defect

## 8. Reproduction instructions

1. Start a disposable PostgreSQL server. Record the version.
2. Create the fixture tables and the conflicting unique row.
3. Run the library call.
4. Read `pg_xact_status()` and the marker from another connection.
5. Record the driver command tag by the method in section 6.

## 9. Impact assessment

Say what an application observes, and what the independent check shows. Separate these when they differ:

- The earlier write's durability
- A later transaction on the same connection
- A commit callback or committed-state flag
- Whether the outcome is unknown rather than rolled back

A later transaction committing shows that the connection could be used again. It does not show that the earlier transaction committed.

## 10. Possible remediation approaches

Pick approaches that fit the library's architecture. Do not recommend one universal fix. For a false success where the driver exposed `ROLLBACK` and the framework reported success, the candidates to consider are:

- Inspect the PostgreSQL command tag on the driver result of `COMMIT`
- Keep that field available on the framework result
- Fail or return a rollback when the completion tag is `ROLLBACK`
- Return an explicit transaction-outcome type
- Invalidate a connection only when its state is still unsafe
- Correct a transaction-manager state transition that marks the outcome committed
- Document the uncertainty when the driver cannot know the outcome

Say which of these the recorded evidence supports, and which were not investigated.
