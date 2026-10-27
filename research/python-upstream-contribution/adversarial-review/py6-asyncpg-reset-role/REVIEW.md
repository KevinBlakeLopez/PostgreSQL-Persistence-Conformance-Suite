# Independent adversarial review of PY-6

Received 2026-10-27. The three exact replacements below were applied the same day to [`../../upstream-drafts/asyncpg-reset-role.md`](../../upstream-drafts/asyncpg-reset-role.md). One further wording change, from the review's source note rather than from a replacement block: `init` is described as documented with type codecs as an example, not as an exclusive use. The review itself was not edited. Nothing here authorizes filing.

**Verdict: READY WITH CHANGES.** **[Judgment]** The narrow claim—committed `SET ROLE` survives the default pool reset—withstands the artifact and source checks. I found no program/output mismatch, incorrect hash, transaction-order mistake, or role-handling change in #1392. Three claims need narrowing: diagnostic silence, the unconditional `init` compatibility prediction, and cleanup. This verifies saved artifacts and source; I did **not** rerun the historical executions. Nothing was edited, committed, filed, posted, or commented on GitHub. This verdict is not permission to file.

**Findings, highest severity first**

1. **“asyncpg reports nothing.” — UNVERIFIED**

   **[Observed—VERIFIED]** The three saved files contain stdout only. They have no stderr, exception-handler output, or diagnostic-log capture. The program prints its four lines after both checkout contexts have exited, but before pool closure and object cleanup.

   **[Source reading—VERIFIED]** The reviewed reset implementation contains an exception-handler diagnostic for certain active-transaction resets. That does not establish that this reproduction emitted one; it demonstrates why stdout alone cannot establish diagnostic silence.

   **Exact replacement:**

   > The saved stdout contains both checkout results; no stderr or asyncpg diagnostic-log capture is included.

2. **“The default reset runs on every release and today does not clear that role, so it is still current on later checkouts. Sending `RESET ROLE` on every release would clear it.” — OVERSTATED**

   **[Source reading—VERIFIED]** Release can close or discard a connection instead of resetting it. For a connection retained for reuse, the role prediction is supported by the implementation.

   **[Source reading—VERIFIED]** `RESET ROLE` restores the connection-time default, which can itself be the role assigned in `init`. In that case, `current_user` need not change. The draft’s two PostgreSQL statements are therefore compatible: an SQL command executed by `init` differs from a connection-time default. The problem is the unconditional “would clear it,” not an inherent contradiction. [PostgreSQL 18 SET ROLE](https://www.postgresql.org/docs/18/sql-set-role.html).

   **[Observed—VERIFIED]** The embedded program supplies neither `init` nor `server_settings`. These variations have no runtime evidence in the supplied artifacts.

   **Exact replacement for those two sentences:**

   > For a reusable connection, source reading predicts that a committed session-level `SET ROLE` in `init` survives the current default reset unless later code changes it. Adding `RESET ROLE` would instead restore the connection-time role setting, or the session user if no such setting exists; it need not change `current_user` when the init-time role already equals that default. These init-time cases were not run.

   **[Source reading—VERIFIED]** The cited `init` lines, 1312–1318, are correct. Type codecs are an **example**, not an exclusive permitted use. `setup` is documented at 1306–1310 and runs before acquisition returns the connection.

3. **“The program creates database … grants `tenant_a` to `app_login`, and drops those three objects at the end.” — OVERSTATED**

   **[Source reading—VERIFIED]** The deletion targets are restricted to the three fixed names. Successful creation flags also prevent ordinary name-collision failures from deleting pre-existing objects.

   **[Source reading—VERIFIED]** Cleanup is not guaranteed: failure to reconnect prevents it; the first failing cleanup statement prevents subsequent statements; cancellation can bypass the cleanup sequence because the outer operation lacks a cleanup `finally`. A connection loss after creation but before acknowledgement can also leave an object whose creation flag was never set.

   **[Observed—VERIFIED]** The saved stdout cannot corroborate cleanup or exit status because printing precedes cleanup. The internal notes’ “Exit 0” and post-run object inventories are not accompanied by separate captures.

   **Exact replacement:**

   > The program creates database `ppcs_repro_asyncpg_role`, role `app_login` (`LOGIN`, with a random password that it does not print), and role `tenant_a` (`NOLOGIN`), grants `tenant_a` to `app_login`, and drops those objects on successful completion; interruption or cleanup failure can leave objects behind.

**Verification supporting the verdict**

**[Observed—VERIFIED]** The embedded Python block is byte-identical to the 5,944-byte file. The complete output block equals the three complete saved files joined with one blank separating line. All internal-note hashes match:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `repro.py` | 5,944 | `82ff6d85750bc5eec484af24102ba3e031d44b1dda1fb47ac405ac18d561314b` |
| `run.rep1.out` | 285 | `a917fb40ccf3fe639a982f0d88c555be440f08701a785920b21e9d68e9f942a7` |
| `run.rep2.out` | 287 | `834ef9d3d81b64d9b350c91bb748b8ecce5b82000e3c57666b8764bdd30fb893` |
| `run.rep3.out` | 287 | `6bf879e7b6bde304ba5160a727a7d83d86751911af015ecfacc29d6211d80b6b` |

**[Source reading—VERIFIED]** The mechanism’s order is:

1. The inner transaction context awaits its commit operation: `transaction.py:70–93`, `175–192`.
2. Only then does the outer acquisition context call pool release: `pool.py:1185–1194`.
3. Pool release awaits the holder’s release operation: `1045–1055`.
4. Without a custom reset callback, the holder awaits `Connection.reset()`: `269–274`.
5. `Connection.reset()` first calls `_reset()`, which rolls back an open transaction, then obtains and executes the reset query: `connection.py:1550–1594`.

The relevant installed-source spans match the tag. The fetched `connection.py` and `pool.py` on `master` and `v0.32.0` are identical. This establishes the source path, not a captured historical SQL trace. [Transaction source](https://github.com/MagicStack/asyncpg/blob/v0.32.0/asyncpg/transaction.py#L70), [pool source](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/asyncpg/pool.py#L269), [reset source](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/asyncpg/connection.py#L1550).

**[Source reading—VERIFIED; judgment]** The docstring splice is accurate. The omitted rollback, cursor, and listener clauses do not introduce a role exception. The subsequent qualification about `get_reset_query` is also acknowledged by the draft. Nevertheless, the explicit statement list gives a maintainer a reasonable contract interpretation under which the implementation behaves exactly as documented. The evidence supports requesting a behavior or documentation decision; it does not settle that contract interpretation.

**[Source reading—VERIFIED]** The PostgreSQL `RESET` page does not document the role exception. The server source does: the `role` entry carries `GUC_NO_RESET_ALL`, and `ResetAllOptions()` skips parameters with that flag. The draft correctly uses server source for this claim. [RESET documentation](https://www.postgresql.org/docs/18/sql-reset.html), [role entry](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/utils/misc/guc_tables.c#L4544), [reset implementation](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/utils/misc/guc.c#L2003).

**[Source reading—VERIFIED]** Upstream still has `master` at `13b01910da3fe01b8241c31cc86eccb1301a2d39`; 0.32.0 remains the latest release checked through PyPI and GitHub. #1293 concerns temporary tables. #1392 remains open and unmerged; its full patch and discussion contain no role-handling change. #270’s comments reject `DISCARD ALL` for compatibility and prepared-statement reasons. [PyPI](https://pypi.org/project/asyncpg/), [master](https://github.com/MagicStack/asyncpg/commit/13b01910da3fe01b8241c31cc86eccb1301a2d39), [#1293](https://github.com/MagicStack/asyncpg/issues/1293), [#1392](https://github.com/MagicStack/asyncpg/pull/1392), [#270](https://github.com/MagicStack/asyncpg/issues/270).

**[Source reading—VERIFIED]** I repeated the nine role/reset searches and broader `role` searches separately for issues and PRs. GitHub Discussions searches for `SET ROLE`, `RESET ROLE`, and `RESET ALL` produced no matching role-reset report; the `SET ROLE` search returned #883, which concerns parameterizing `SET`. **[Judgment]** These results reduce duplicate risk; they do not prove no report exists. [Discussion #883](https://github.com/MagicStack/asyncpg/discussions/883).

**Sentence ledger**

Line numbers refer to the draft as reviewed, before the three replacements above were applied. Repeated claims are listed once with their relevant occurrences. **Observed** below means inspection of artifacts or the current environment, not a fresh database execution.

| Location | Claim | Evidence classification and assessment |
|---|---|---|
| Title | `SET ROLE` survives the default pool reset | **Observed—VERIFIED:** saved checkout results support the narrow claim. |
| 55 | Tested asyncpg version is 0.32.0 | **Observed—VERIFIED:** all three outputs and current installed metadata agree. |
| 55 | Quoted source is unchanged on `master 13b01910d` | **Source reading—VERIFIED:** relevant text and line numbers match. |
| 56 | Server reports PostgreSQL 18.6, Debian build specified | **Observed—VERIFIED:** present in each saved server-version line. |
| 56 | Historical server used local Docker image `postgres:18.6` | **Observed—UNVERIFIED:** stdout identifies the server build, not its image or topology. |
| 57–58 | No PostgreSQL SaaS was used | **Observed—UNVERIFIED:** no independent historical topology capture supplied. |
| 58 | Reproduction was local | **Observed—UNVERIFIED:** recorded account; not independently established by stdout. |
| 59 | Python version was 3.13.11 | **Observed—VERIFIED currently:** installed interpreter agrees; historical stdout does not print Python’s version. |
| 60 | Platform was macOS 26.6.2, arm64 | **Observed—VERIFIED currently:** host checks agree; historical execution not independently captured. |
| 61 | No PgBouncer was used | **Observed—UNVERIFIED:** no historical endpoint/topology capture. |
| 62 | Installed with pip, using a wheel | **Observed—VERIFIED metadata:** `INSTALLER=pip` and the stated wheel tag are present; original installation command not independently checked. |
| 63 | Local Cython build question is inapplicable | **Observed—UNVERIFIED historically:** consistent with metadata and the recorded wheel account. |
| 65, 86 | Reproduction uses asyncio | **Source reading—VERIFIED:** program invokes `asyncio.run`; saved artifacts are consistent with that program. |
| 65, 86 | There were three runs | **Observed—VERIFIED artifact count:** three distinct saved outputs; executions were not rerun. |
| 65 | uvloop was not run | **Source reading—VERIFIED scope declaration:** no uvloop result is presented. |
| 67 | Reset documentation describes a session resembling a new connection | **Source reading—VERIFIED.** |
| 67 | Documentation says session configuration variables return to defaults | **Source reading—VERIFIED:** accurate quotation/paraphrase; breadth remains a contract judgment. |
| 67–74 | Pool documentation lists the four displayed statements | **Source reading—VERIFIED:** lines 1329–1332 match. |
| 76 | Those statements omit `RESET ROLE` | **Source reading—VERIFIED.** |
| 76, 123–125, 228–233 | Checkout 1 commits its session-level role change before release | **Source reading—VERIFIED:** nested context order and transaction implementation establish this. |
| 76, 308 | Checkout 2 still reports `current_user=tenant_a` | **Observed—VERIFIED:** all saved outputs agree. |
| 76 | Checkout 2 uses the same backend | **Judgment:** strongly supported by matching PIDs and the one-connection sequential pool; inferred rather than independently traced. |
| 76, 308 | `session_user` remains `app_login` | **Observed—VERIFIED:** all saved outputs agree. |
| 76 | asyncpg reports nothing | **UNVERIFIED:** finding 1. Replaced in the draft. |
| 80 | Use a disposable server | **Judgment:** appropriate execution constraint; not an experimental result. |
| 80 | Admin connection needs database- and role-creation privileges | **Source reading—VERIFIED:** required by the executed SQL; successful use also depends on ordinary connection/grant permissions. |
| 80 | Program creates the named reproduction database | **Source reading—VERIFIED:** fixed SQL target. |
| 80 | Program creates `app_login` with `LOGIN` | **Source reading—VERIFIED.** |
| 80 | Its password is random | **Source reading—VERIFIED:** generated with `secrets.token_hex(24)`. |
| 80 | Program does not print that password | **Source reading—VERIFIED:** print expressions omit it; failure text passes through redaction. |
| 80 | Program creates `tenant_a` with `NOLOGIN` | **Source reading—VERIFIED.** |
| 80 | Program grants `tenant_a` to `app_login` | **Source reading—VERIFIED.** |
| 80 | Program drops all three objects at the end | **OVERSTATED:** finding 3. Replaced in the draft. |
| 80, 122 | Pool contains one connection | **Source reading—VERIFIED:** `min_size=max_size=1`. |
| 80, 122, 308 | Pool logs in as `app_login` | **Source reading + observed—VERIFIED:** constructed DSN and saved `session_user` agree. |
| 80, 259–262 | Pool creation omits `reset=` | **Source reading—VERIFIED.** |
| 83, 131 | Displayed command supplies the required URL through the environment | **Source reading—VERIFIED syntax; NOT CHECKED execution:** authentication must suit the disposable server. |
| 86 | The users agreed across runs | **Observed—VERIFIED:** the two identity fields agree across all three saved repetitions. |
| 86, 94–105 | Recorded PIDs are 93, 103, and 113 | **Observed—VERIFIED.** |
| 86, 94–105 | Both checkouts in each run print the same PID | **Observed—VERIFIED.** |
| 91–106 | Quoted output includes the complete saved stdout files | **Observed—VERIFIED byte comparison:** no saved-file content omitted. Whether those files captured every historical stdout byte is not independently provable here. |
| 113–288 | Embedded program is the supplied `repro.py` | **Observed—VERIFIED byte comparison.** |
| 114 | Program shows the role after default pool reset | **Source reading—VERIFIED mechanism; observed results agree.** |
| 116 | Program reads `DATABASE_URL` | **Source reading—VERIFIED.** |
| 116 | Program exits if the variable is unset | **Source reading—VERIFIED.** |
| 116–120 | Admin-database connections serve object setup and teardown | **Source reading—VERIFIED:** no application workload runs through those connections. |
| 123–126 | Checkout 1 sets the role and reads both user identifiers | **Source reading—VERIFIED; saved values agree.** |
| 125 | Releasing the retained connection invokes default reset | **Source reading—VERIFIED:** release path traced above; no historical wire capture. |
| 125–126 | Checkout 2 reads identities and backend PID | **Source reading—VERIFIED; saved output contains those fields.** |
| 128–129 | Program prints asyncpg version, server version, identities, and both PIDs | **Source reading + observed—VERIFIED.** |
| 228–229 | An open transaction would be rolled back before the reset query | **Source reading—VERIFIED.** |
| 228–229 | Such a rollback would undo this transaction’s `SET ROLE` | **Source reading—VERIFIED:** PostgreSQL documents transactional `SET` behavior; fresh control not run. |
| 294 | psql’s `SET ROLE; RESET ALL` check retained `tenant_a` | **Source reading—VERIFIED historical README quotation:** no raw psql output file exists. |
| 294 | Subsequent `RESET ROLE` restored `postgres` in that session | **Source reading—VERIFIED historical README quotation:** separate older superuser check. |
| 294 | psql observation belongs to these three asyncio runs | **Judgment: not claimed.** It appears under a separate PostgreSQL section; the body does not explicitly merge the executions. |
| 296 | `RESET ROLE` restores a configured connection-time role | **Source reading—VERIFIED:** PostgreSQL documentation supports it. |
| 296 | Otherwise it restores the session user | **Source reading—VERIFIED.** |
| 296 | Any user may execute that form | **Source reading—VERIFIED.** |
| 296 | Server flags `role` with `GUC_NO_RESET_ALL` | **Source reading—VERIFIED:** table entry and skip logic both inspected. |
| 298 | `server_settings={'role': ...}` was not run | **Source reading—VERIFIED scope declaration:** no result for it is presented or inferred as measured. |
| 302–304 | Docstring reference and quoted splice are accurate | **Source reading—VERIFIED:** correct on the tag and checked master. |
| 304 | Omitted middle changes the role claim | **Judgment: no.** It enumerates other reset actions without introducing a role exception. |
| 306 | Docstring identifies `get_reset_query` as the default-query basis | **Source reading—VERIFIED.** |
| 306 | Pool reset reference at 1326–1332 is correct | **Source reading—VERIFIED.** |
| 312 | Append capability-gated `RESET ROLE` | **Judgment/proposal:** no implementation or compatibility result established. |
| 312 | #1392 demonstrates capability-gated `DISCARD TEMP` | **Source reading—VERIFIED patch.** |
| 312 | Update reset and pool documentation alongside a behavior change | **Judgment/proposal.** |
| 313 | Documentation correction is an alternative | **Judgment/proposal:** the exact statement list already supports a narrower contract interpretation. |
| 313 | Document a custom callback adding `RESET ROLE` | **Judgment/proposal:** callback mechanism exists; this workaround was not executed. |
| 315 | Draft does not propose `DISCARD ALL` | **Source reading—VERIFIED text.** |
| 315 | #270 declined `DISCARD ALL` | **Source reading—VERIFIED issue comments.** |
| 317 | `init` runs when each physical connection is created | **Source reading—VERIFIED:** documentation and implementation agree. |
| 317 | Type codecs are documented at 1312–1318 | **Source reading—VERIFIED:** an example, not an exclusive restriction. The draft now says “as an example.” |
| 317 | Default reset runs on every release | **OVERSTATED:** connections can instead close or be discarded. That sentence was removed. |
| 317 | An init-set role remains current on later checkouts | **Source reading:** conditional prediction; **NOT CHECKED** at runtime. Replaced. |
| 317 | Adding `RESET ROLE` would clear that role | **OVERSTATED:** finding 2. Replaced. |
| 317 | Applications can assign a role through `setup` on acquisition | **Source reading—VERIFIED:** callback runs before the connection is returned; this application pattern was not run. |
| 319 | #1293 concerns surviving temporary tables | **Source reading—VERIFIED.** |
| 319 | #1392 concerns surviving temporary tables | **Source reading—VERIFIED.** |
| 319 | #1392 remains open | **Source reading—VERIFIED current upstream state.** |
| 319 | #1392 is unmerged | **Source reading—VERIFIED current upstream state.** |
| 319 | Neither addresses `SET ROLE` | **Source reading—VERIFIED:** inspected issue, complete PR patch, and PR discussion. |

**Checks not run**

- **NOT CHECKED—runtime:** a fresh three-run reproduction, stderr capture, SQL statement logging, or wire tracing. Docker socket access was denied by the sandbox. `ppcs-postgres` and port 55435 were not used.
- **NOT CHECKED—runtime:** `init`, startup roles through `server_settings`, a custom reset callback, uvloop, master, or PostgreSQL-compatible forks.
- **NOT CHECKED—runtime:** cleanup failures, cancellation, lost acknowledgements, or name-collision execution tests. The cleanup findings are source reading.
- **NOT CHECKED—historical provenance:** independent confirmation of the removed container’s identity, image digest, command, exit statuses, or before/after object inventories. Matching hashes verify the current artifacts, not historical execution.
- **Source reading—VERIFIED:** “non-superuser” correctly describes the subject pool session: both created roles default to `NOSUPERUSER`, and the saved subject `session_user` is `app_login`. The administrative setup connection is separate. No live `rolsuper` query was performed.
