# Shared Ruby protocol

`adapters/ruby/lib/ppcs.rb` is the newline-delimited JSON protocol from `docs/protocol.md`, plus the category C and D faults the catalog already defines. It is not a second conformance runner.

`ruby-pg-control` and `activerecord` both load it. Their manifests list `../ruby` in `shared`, so the source digest includes this directory.

The ruby-pg modes are not harness kind `control`. A manifest whose every mode is kind `control` is auto-run beside other adapters and its expectations become part of `case_controls`. That would change every existing adapter's run and the CI comparison. `jdbc-control` and `pdo-control` already avoid that. This library does not change the harness.
