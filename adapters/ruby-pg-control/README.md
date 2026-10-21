# ruby-pg control

Direct `PG::Connection` transactions for PPCS. This is the driver control for the Active Record adapter. It is not a framework, and it is not a second suite-wide case-control gate. `pg-control` remains that gate. The mode kinds follow `jdbc-control` and `pdo-control` for that reason.

## Versions

Pinned in `Gemfile` and `Gemfile.lock`:

- Ruby 4.0.7 (normal maintenance; latest patch of the 4.0 branch as of 2026-10-21)
- pg 1.7.0 (released 2026-10-02; requires Ruby >= 3.1)
- PostgreSQL 18.6, the disposable server in `compose.yaml`

Ruby 4.0.7 was selected from [ruby-lang.org releases](https://www.ruby-lang.org/en/downloads/releases/) and the [maintenance branches](https://www.ruby-lang.org/en/downloads/branches/). pg 1.7.0 is the current stable gem and ships a binary built with PostgreSQL 18.6 libraries.

## Setup

```sh
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"   # if /usr/bin/ruby is still 2.6
cd adapters/ruby-pg-control
bundle install
ruby -I../ruby/lib ../ruby/test/commit_outcome_test.rb
```

## Run

From the repository root, with the disposable server up (`pnpm run pg:up`):

```sh
node harness/run.mjs --adapter=ruby-pg-control --repeat=3
```

`run.sh` prefers Homebrew Ruby when that binary exists, then `bundle exec ruby main.rb`.

## What correct checks

`PG::Connection#transaction_status` is `PQTRANS_IDLE` after PostgreSQL accepts `COMMIT` and after it answers that statement with command tag `ROLLBACK`. The public field that distinguishes those replies is `PG::Result#cmd_status`. `correct` reports committed only for the tag `COMMIT`, rolled back only for the tag `ROLLBACK`, and failed for any other tag or a raised error. `unsafe` reports committed whenever `COMMIT` does not raise.
