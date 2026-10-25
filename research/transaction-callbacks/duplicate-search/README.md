# Duplicate search

Searched 2026-10-24 and 2026-10-25 (UTC). Written by: Claude Opus 5.5 (max). A delegated search covered php-src and bugs.php.net; I spot-checked its two most important hits and did the Laravel part myself. Nothing was posted.

The questions:

- **A.** Is `PDO::commit()` returning `true` for a `COMMIT` answered with `ROLLBACK` already reported?
- **B.** Is Laravel running after-commit callbacks for such a transaction already reported?
- **C.** What do Laravel's documentation and maintainers say about catching database exceptions inside `DB::transaction()` on PostgreSQL?

The conclusions are in [`../stage-4-review.md`](../stage-4-review.md#duplicate-assessment).

| File | What it records |
| --- | --- |
| `php-src-queries.log` | 33 GitHub searches of php-src issues and pull requests, each with its hit count |
| `php-src-label-pdo_pgsql.tsv`, `php-src-label-pgsql.tsv`, `php-src-label-pdo-core.tsv` | Every issue and pull request under the labels "Extension: pdo_pgsql" (149), "Extension: pgsql" (211) and "Extension: pdo (core)" (266), whose titles were all read. Columns: number, state, date, kind, title |
| `bugs-php-net-queries.log` | 11 searches of bugs.php.net through its RSS endpoint, with hit counts |
| `laravel-queries.log` | 16 searches of laravel/framework and laravel/docs, with results |

Limits:

- **GitHub search.** It matches words, so an issue that describes the symptom in other words can be missed. The label listings cover only labelled items.
- **bugs.php.net.**
  - Its search form now requires a login. The RSS endpoint does not, but it searches only the summary, the description and the author address, never comments.
  - The delegated search also downloaded every bug in the PDO and PostgreSQL packages: 1,512 bugs, kept outside the repository. It then searched their summaries and descriptions locally.
  - The comment on bug #37870 quoted in the review was found by reading that bug's page.
- **Discussions.** laravel/framework discussions were searched through GraphQL, with 4 queries. laravel/docs has no discussions.
- **Not searched.** Doctrine DBAL, Symfony, and other consumers of pdo_pgsql.
