Written by: GPT-6 / Codex (effort setting not exposed).

# Search record, 2026-10-26

- [queries.json](queries.json): 39 initial queries, with the requested result sample size (`n=12`).
- [supplement.json](supplement.json): nine adaptive queries, including replacements for invalid numeric issue searches.
- [totals.tsv](totals.tsv): all 48 totals, result completeness and timestamps; two numeric queries are explicitly invalidated.
- [inspection.md](inspection.md): 52 eligible code/configuration entries read at exact commits, with the counted sample and exclusions for each finding.

The 48 GitHub requests comprise **29 issue searches and 19 code searches**. They ran through an unchanged copy of the repository's [paced_search.py](../../filed-items-production-relevance/paced_search.py), in one process at a time. Its pacing enforces seven seconds between code-search dispatches and 2.2 seconds between issue-search dispatches. Its printed UTC timestamp is captured before waiting for the pacing lock, so timestamps alone need not be seven seconds apart. The copied helper's lock/state coordinated these assessment processes; it did not share lock state with independent sessions using the original helper. No concurrent searches from another session were detected or measured. Actual cross-session aggregate rate usage is therefore not established.

All queries and reads occurred on October 26, 2026. GitHub query logs span 17:18–17:27 UTC. Direct issue/comment, contents, commit and tree reads followed. The assessed checkout base is `origin/main` at `4bf5195f954e482b8e8505b013559b7d043bc368`; no remote refresh was performed.

Legacy code search matches loose tokens. Repeating `DB::transaction` does not require two occurrences or establish nesting. Several returned files do not contain the complete queried shape. Some `-path` exclusions did not remove framework copies, virtual environments or harvested code. Those were excluded manually from the eligible inspection denominator. Code/configuration samples are convenience samples, neither random nor exhaustive. A count measures matching files; a fraction describes only the stated inspected scope.

Two bare-number issue queries matched issue IDs rather than the conjunction of their text terms. Their totals of 52,069 and 51,904 are retained for audit but excluded from every exposure inference. Replacements add `in:body`. Likewise, the `d-loss` comments search did not return the known #545 comments; those were fetched directly. Empty searches are scoped results, not absence claims.

The ledger lists every counted entry. Additional supporting reads include framework source, configuration/dependency files, negative examples and known upstream threads. These do not silently enlarge the denominators. Named incident reports were read through issue bodies/comments, not inferred from their titles. Full issue records, search responses and fetched third-party files remain outside the publication artifact. No downloaded application or library code was executed.

Other web reads: MySQL 8.4 InnoDB Error Handling was fetched successfully. A direct bugs.php.net #37870 read failed; two scoped web queries did not recover that report. It remains inherited evidence from Stage 4, not a newly verified source. grep.app was not used. GitHub Discussions and Laravel community forums were not searched in this pass.
