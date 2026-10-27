# Draft: thank-you on psycopg/psycopg#1453

**Not posted.** Prepared 2026-10-27. Written by: Grok 4.7.

`dvarrazzo` closed #1453 on 2026-10-27 and explained the contract: https://github.com/psycopg/psycopg/issues/1453#issuecomment-6443758485 This comment thanks him. It does not ask for a change.

Destination, after approval of this exact text: a comment on https://github.com/psycopg/psycopg/issues/1453

**Before posting:**

1. Get approval of the exact text and of the destination.
2. Re-check #1453. If a later comment has arrived, stop and adapt this.
3. Post it as `KevinBlakeLopez`. Do not open a new issue.

**Left out on purpose:** `Connection.transaction()`, `Transaction.status`, SQLAlchemy, Django, and psycopg2. His comment did not mention them. This draft does not add them.

Everything between the two rules below is the proposed comment.

---

Thank you for spelling this out.

I had treated a normal return from `commit()` as a successful commit. After a caught error, the caller is responsible for the connection, and `Connection.info.transaction_status` is the check before `commit()` or `rollback()`. I'll leave `commit()` as it is.

---
