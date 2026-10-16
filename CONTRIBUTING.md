# Contributing

PPCS is only as credible as its weakest adapter. These rules keep the evidence comparable across frameworks and honest about what it shows.

## Adding an adapter

An adapter runs catalog cases with **one framework's own APIs**, as an application would use them. It can be written in any language: it is a program that speaks the protocol in `docs/protocol.md` on stdin and stdout.

1. **Create `adapters/<name>/`**, as its own project, with:
   - its own build file and a committed lockfile (for example `package.json` with `pnpm-lock.yaml`, `pyproject.toml` with a lock, or `pom.xml`);
   - exact, pinned versions of the framework and its driver.
   For a JavaScript adapter, `scripts/setup.sh` installs it with `pnpm install --frozen-lockfile`. For another language, extend `scripts/setup.sh` with that ecosystem's equivalent frozen install.
2. **Write `adapter.json`** (`docs/protocol.md`, "Manifest"):
   - the command to run;
   - the modes, with `native` first;
   - the cases you implement (`implements`);
   - the cases your framework's supported API cannot express (`unsupported`), each with a reason.
3. **Implement each case in the framework's ordinary style:** its managed transaction API, its nested-transaction API, its ordinary write API. Read `pg_current_xact_id()` and `pg_backend_pid()` through the transaction's own connection at each checkpoint.
4. **Report the API's outcome**:
   - `reported` is `committed`, `rolled_back` or `failed`;
   - `basis` says what was observed;
   - `contract` states the framework's contract that gives the observation its meaning. Quote the documentation or the source at the pinned version, and name where the text comes from. The report shows this text for every FAIL.
5. **Run the controls and your adapter**:

   ```sh
   pnpm run test:methodology && node harness/run.mjs --adapter=<name>
   ```

   Your adapter must pass `CTL-01` before its other results mean anything.

## Rules that protect the evidence

- **Native means native.** Do not patch, wrap or configure the framework to change the behaviour under test in the `native` mode. A documented non-default option is a `configured` mode. A mitigation in application code is a `hardened` mode. Both are separate columns, and neither replaces the native result.
- **Do not make a case pass.** If your framework fails a case, the FAIL is the evidence. Report it accurately: the case states the invariant, and the result states the conditions.
- **UNSUPPORTED is not a way out.** Declare a case UNSUPPORTED only when the framework's supported API has no way to express the behaviour, for example no propagation mode that promises an independent transaction. A missing convenience API is not a reason. If you have not written a case yet, leave it out of both lists: it is then NOT_RUN.
- **Label faults truthfully.**
  - The runner injects category B faults (connection termination).
  - If your adapter injects faults in its own driver layer, report how often each fired, and keep the category: C for errors injected in the client, D for driver or ORM state manipulation.
  - A client-side simulation is never described as a network failure.
- **No claims of defects.** Results, commit messages and documentation describe observations and invariants. Whether a FAIL is a defect is for the framework's maintainers to judge, against their own contract.

## Changing a specification

Specifications live in `specifications/transactions.v1.json` and are described in `docs/specifications.md`; change both together.

- **Changing a case's steps, invariants or preconditions:** raise the case's `version`.
- **Changing what a family asserts:** raise the family's `version`.
- **Never edit an invariant to accommodate a framework.** If a framework's contract genuinely differs, add a case or a family that states the other behaviour explicitly.

`harness/lib/classify.mjs` holds the classification rules. Every rule change needs a unit test in `harness/test/unit/`. If it affects how controls or misbehaving adapters are classified, it also needs a methodology test.

## Dependency discipline

- **Pin exact versions** and commit lockfiles. Install only with `--frozen-lockfile` (or the ecosystem's equivalent).
- **Upgrade one thing at a time.** A framework or driver upgrade is its own change: a new lockfile, plus a run compared with `--expect` against the run before it, so that any change in classification is visible.
- **Do not allow dependency install scripts.** pnpm does not run them unless they are allow-listed, and no project here allow-lists any.
- **Add dependencies sparingly.** The harness depends only on `pg`, plus `ajv` for the tests.

## Before you send a change

```sh
pnpm run setup            # frozen-lockfile installs
pnpm run test             # classification rules, no database
pnpm run pg:up
pnpm run test:methodology # controls and fixtures through the real runner
pnpm run ppcs             # the whole suite
pnpm run pg:down
```

Never point PPCS at a database you care about. The runner refuses any server whose `cluster_name` is not the token `pg:up` wrote, and it drops only the databases it created. The rule still stands.
