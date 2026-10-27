# Thank-you on psycopg/psycopg#1453

**Posted 2026-10-27** as `KevinBlakeLopez`: https://github.com/psycopg/psycopg/issues/1453#issuecomment-6451216590 at 2026-10-27T19:12:17Z. Compared through the API. The issue was still closed, state reason `completed`.

The posted body is the text below. It does not match an earlier draft. That draft opened "Thank you for spelling this out." and, in the committed copy, ended with "I'll leave `commit()` as it is." The posted comment uses the shorter opening and omits that line.

**Left out, as posted:** `Connection.transaction()`, `Transaction.status`, SQLAlchemy, Django, and psycopg2.

---

Thx for explaining!

I treated a normal return from commit() as a successful commit. After a caught error, the caller is responsible for the connection, and Connection.info.transaction_status is the check before commit() or rollback().

---
