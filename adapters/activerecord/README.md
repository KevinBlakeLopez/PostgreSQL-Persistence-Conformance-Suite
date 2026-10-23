# Active Record adapter

Active Record 8.1.4 on the pg 1.7.0 adapter, without a Rails application. The scored API is `ActiveRecord::Base.transaction` and `create!`. Nested cases use `transaction(requires_new: true)`. Migrations use `ActiveRecord::MigrationContext`.

The findings are [`FINDINGS.md`](FINDINGS.md). The three-repetition run is [`reports/examples/2026-10-23T21-46-47Z-b3b7bd`](../../reports/examples/2026-10-23T21-46-47Z-b3b7bd/summary.md). It re-records [`reports/examples/2026-10-21T19-39-32Z-b559f2`](../../reports/examples/2026-10-21T19-39-32Z-b559f2/summary.md) with `form` reported as a string, and every cell the two runs share has the same classification.

## Versions

Pinned in `Gemfile` and `Gemfile.lock`:

- Ruby 4.0.7, the latest patch of the 4.0 branch as of 2026-10-21. Ruby 4.1.0-preview1 was not used.
- Active Record 8.1.4 (24 September 2026). Rails 8.1 requires Ruby 3.2 or newer. Rails 8.2.0 is not a published gem.
- pg 1.7.0 (2 October 2026).

The disposable server is PostgreSQL 18.6 from `compose.yaml`. The pg gem's `PG.library_version` in this run was 180006.

## Setup

```sh
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"   # when /usr/bin/ruby is older
cd adapters/activerecord
bundle install
```

## Run

From the repository root, with `pnpm run pg:up`:

```sh
node harness/run.mjs --adapter=activerecord --repeat=3
```

`run.sh` prefers Homebrew Ruby when that binary exists, then `bundle exec ruby main.rb`.

The follow-up probe is not a PPCS case:

```sh
bundle exec ruby probes/tx01a_followups.rb
```

It reads `.ppcs-instance.json`, creates a database, and drops it. The recorded output is `probes/tx01a-followups.json`.
