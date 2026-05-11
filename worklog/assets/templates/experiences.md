# Experience Library

> Newest first. Keep original wording when deprecating. Mark stale or wrong content with `~~...~~` and add a reason.

## Tag index
- `#sqlalchemy` (3) · `#react` (2) · `#debug` (5)

---

## 2026-05-11

<!-- exp-meta:
id: exp-2026-05-11-001
tags: [sqlalchemy, orm, audit, pitfall]
project: my-project
confidence: high
status: active
verified_against: SQLAlchemy 2.0.30
last_verified_at: 2026-05-11
supersedes: null
superseded_by: null
pinned: false
deprecated_at: null
deprecated_reason: null
-->

### SQLAlchemy cascade plus passive_deletes skips ORM delete hooks {#exp-2026-05-11-001}

When a relationship uses `cascade="all, delete"` together with `passive_deletes=True`, deletes can be enforced by the foreign key rather than the ORM, so ORM delete hooks do not run.

**Tags**: `#sqlalchemy` `#orm` `#audit` `#pitfall`  
**Confidence**: high  
**Source**: [worklog](./my-project/2026-05-11/cascade-bug.md)
