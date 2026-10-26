# Production relevance

Adopted by the maintainer on 2026-10-26. Written by: Claude Opus 5.5 (max).

A PPCS finding shows that a framework's report can disagree with what PostgreSQL did. This page sets how a finding records whether that matters to real applications: what real code and reports show, how natural each trigger is, and what is still unknown.

It applies to findings: the items in a tracker, and the findings of a study. It does not apply to each suite result. A FAIL is a counterexample to an invariant, not a defect report ([`research-master-plan.md`](research-master-plan.md)).

## Search before building an example

Before building an example application or a demonstration for a finding, search public code for applications and libraries that already have the shape. If you find one, run its own code where you can. Build an example only when the search finds nothing usable, and call it constructed.

- **A constructed example uses transactions reasonably.** Every write inside an all-or-nothing transaction is essential to that unit. Optional work runs in its own transaction. CHK-12 was re-run for this reason: its first trigger, a best-effort analytics write inside the order's transaction, is not reasonable application code.
- **A mechanism check may use any trigger.** Its README says when the trigger is not a recommended design, as CHK-15's does.

## The section

Each finding carries a dated section headed **Production relevance**, or links a search record that covers it. A finding with neither has not been searched. Add the section when the finding is ranked, queued for an upstream post, or used in an example.

Record these fields in this order. Write "not assessed" for a field you have not done; do not leave it out.

1. **Consequence.** What goes wrong for the application: a lost write, a false success, a callback for the wrong outcome, unsafe connection reuse, duplicated work, or only an unexpected error. Say whether anything tells the caller.
2. **Triggers.** One entry per trigger, because the evidence differs by trigger. PY-2 has a production report through a caught deadlock, while its caught client timeout is not reasonable application code. For each trigger:
   - **In production:** the event, and whether it happens in real deployments (yes, no or unknown), with the evidence.
   - **In our runs:** how PPCS produced it: a real database error through an ordinary API, an injection, or a simulation. This is the master plan's dimension 7, production reachability. Category C and D faults are client-side: they show a path, not how often it occurs.
   - **Code shape:** the code the trigger needs, and whether a competent developer would write it. Redraw the transaction boundary and the error handling from scratch. If a reasonable design would not put that code there, say so.
   - **Real-world evidence:** the strongest kind found (below). Link code at a commit and lines, and issues by number. Say who reported it (the project's owner, a maintainer, a user), the project's size where known, and what we checked ourselves.
3. **Reproduced on real code.** Whether a check ran the real-world code from field 2, rather than a re-creation of it, and which check. Say what ran: a call sequence copied from an application is not the application.
4. **Searches.** The date, where, the queries or a link to their log, the totals, and an inspected sample: "k of n inspected hits have the failing shape". A count without an inspected sample counts files, not exposure.
5. **Likelihood (judgment).** Low, moderate or high, from two questions: how common is the code shape on that stack, and how often does the trigger fire once the code exists? Label it a judgment, and date it.
6. **Not established.** What the evidence does not show, such as frequency, a report on this driver, or a run of the application itself.

In a tracker, a trigger's four parts can share one line, and the evidence can be a link to where it is recorded rather than a copy. PY-2 in the [Python tracker](../research/python-upstream-contribution-tracker.md) is an example.

## Kinds of real-world evidence

Strongest first. This is the list of the [Python real-world evidence page](../research/python-upstream-contribution/real-world-evidence/README.md), with one kind added, exposed code:

- **Production:** a report that quotes production logs or metrics.
- **Incident:** a person or project describes the failure on a real deployment.
- **Audit:** a project's own report, checked against its code.
- **Acknowledged:** a maintainer states the pattern exists in their code, without a stated consequence.
- **Harmful consumer:** real code that turns the behaviour into damage.
- **Exposed code:** real code, read at a commit, that has the failing shape, with no failure reported. The page called its PY-5 instance "adoption".
- **Other ecosystem:** the same mechanism reported or fixed in another language's driver or framework.
- **Pattern count:** code-search totals.

Production and incident reports show that the failure happened somewhere, not how often. The other kinds show exposure, not occurrence.

## Searching

- A search that finds nothing is a result with a scope, not proof of absence. Record the scope, and do not extend it to the whole ecosystem.
- Look for evidence against the finding too: hits that handle the error correctly, documentation that puts the duty on the caller, and maintainers who call the shape misuse.
- A search contacts no one. Telling a project that its code is exposed is an upstream post, and needs approval ([`AGENTS.md`](../AGENTS.md), rule 9).
- Treat downloaded application code as untrusted. Install it in an isolated environment, and run it only against a disposable server (rule 6).

## Kept separate

This section does not rate severity or the contract.

- Severity and feasibility stay ranks of their own: A and B in the Python tracker.
- Contract status stays in each item's Confidence field, as in "CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN".
- Do not merge relevance and severity into one score ([`AGENTS.md`](../AGENTS.md), rule 8).

## Coverage on 2026-10-26

The Python real-world evidence page covers PY-1 to PY-9, PY-15 and PY-20 to PY-24, searched on 2026-10-26, and CHK-16's README covers PY-25. The tracker rates every Python item: the scheduled ones in their own sections, the others in its "Production relevance (2026-10-26)" section. Every non-Python finding filed upstream (21 of them) is searched and rated in [`research/filed-items-production-relevance/`](../research/filed-items-production-relevance/README.md). No other finding has been searched: the unfiled drafts and the studies' other findings have no section yet.
