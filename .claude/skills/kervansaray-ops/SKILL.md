---
name: kervansaray-ops
description: >
  Operational runbook for shipping a backend/tool/prompt/schema change in the
  Kervansaray repo — verify, commit, deploy, live smoke-test. Use whenever you
  edit anything under src/kervansaray, scripts/, or alembic/ and need to test
  it before or after pushing; when adding a new LLM tool; when adding or
  changing a Flask route; when writing an Alembic migration; or when running
  a live query against the running demo. Companion to AGENTS.md (who/what —
  agent coordination, lanes) and docs/PARALLEL_WORKFLOW.md — this file is
  how, not who.
---

# Kervansaray Ops

Commands and checklists this repo's work repeats every session. If you
haven't already, read `AGENTS.md` first (coordination) — this is execution.

## The ship loop

Every backend/tool/prompt change follows this. Don't skip steps under time
pressure — the container-test step is what catches ruff/pytest regressions
*before* they hit a shared `main` that Antigravity is also building on.

1. **`git fetch && git status`** — before editing. This checkout is shared
   with Antigravity on the same server; `git status` may show *their*
   uncommitted work. Never `git add -A` blindly — `git add` only the files
   you touched.
2. Make the change.
3. **Verify in a throwaway container** (the `app` image has no dev deps and
   doesn't mount `tests/`; the host has no Python venv):
   ```bash
   docker compose exec -T db psql -U kervansaray -c "DROP DATABASE IF EXISTS kervansaray_test" >/dev/null
   docker compose exec -T db psql -U kervansaray -c "CREATE DATABASE kervansaray_test" >/dev/null
   docker run --rm --network kervansaray_default -v "$PWD":/w -w /w \
     -e DATABASE_URL="postgresql+psycopg://kervansaray:kervansaray@db:5432/kervansaray_test" \
     python:3.11-slim sh -c "pip -q install -e '.[dev]' >/dev/null 2>&1; ruff check .; pytest -q"
   ```
   Full suite is ~170 tests / ~5 min. For a fast inner loop, point `pytest -q`
   at the specific `tests/test_*.py` files your change touches; run the full
   suite before the final commit.
4. **Commit.** Message body in Turkish, imperative, explains *why* not just
   *what*. If the message contains a `"` or spans multiple lines with
   apostrophes, **don't** put it in `-m "..."` — a stray quote breaks the
   shell mid-heredoc and half-executes. Write it to a scratch file and use
   `git commit -F <file>`. Trailer:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   ```
5. **`git push origin main`.**
6. **Deploy — bind mount, so restart is enough:**
   ```bash
   docker compose restart app && until curl -sf localhost:8000/healthz >/dev/null 2>&1; do sleep 2; done
   ```
7. **Live smoke-test** (see below) against `localhost:8000` directly — skips
   Caddy, so it won't catch a missing proxy route (see "New Flask route").
8. **`curl -s -XPOST localhost:8000/api/rate-limit/reset`** after testing —
   your smoke queries burned the demo's per-IP quota (10/min), and the next
   real visitor from this IP shouldn't hit it.
9. Update `docs/PARALLEL_STATUS.md`: mark your claim done, leave Antigravity
   a dated note on anything it touches or should know about.

## Live smoke-test pattern

An LLM round-trip takes 5–90s (NVIDIA latency, sometimes a domain-hint
retry doubles it) — too slow for a foreground call you're waiting on
one-at-a-time. Batch queries into one backgrounded script and poll:

```bash
q() { curl -s -XPOST localhost:8000/api/query -H 'content-type: application/json' \
  -d "{\"query\":$1,\"use_cache\":false}" | python3 -c \
  'import sys,json;d=json.load(sys.stdin);tc=d.get("tool_call") or {};print(tc.get("name"),tc.get("args"),"->",(d.get("narrative") or "")[:200])'; }
q '"sistemde kaç araç kayıtlı"'
q '"34 VIP 99 plakalı aracı sorgula"'
curl -s -XPOST localhost:8000/api/rate-limit/reset >/dev/null; echo done
```
Run with `run_in_background: true`, then poll the output file with
`until grep -q "^done" <file>; do sleep 5; done` rather than a fixed sleep —
the harness blocks bare `sleep`, and total latency varies run to run.

`use_cache:false` is required — curated demo questions (the 6 scenario
prompts + suggested-question chips) are pre-warmed in `demo_cache` and
return instantly without touching the LLM at all, which defeats the point
of a smoke test.

## New LLM tool checklist

Kervansaray freezes the *count* of tools (7, as of this writing) and grows
capability through parameters instead — a 6–7-tool ceiling is where small
models (Nemotron 3.5, Gemini Flash) hold routing accuracy; an 8th tool
competing for the same decision measurably hurts it. Before proposing a new
tool, check whether the need is really a missing **parameter** on an
existing one (`query_events`, `aggregate_events`) or a genuinely orthogonal
question (`registry_summary` counting `vehicles` vs. `v_events` was
orthogonal enough to earn tool #7).

Either way, one addition touches all of:

1. `src/kervansaray/tools/<name>.py` — the function, returns `ToolResult`.
2. `src/kervansaray/tools/__init__.py` — export.
3. `src/kervansaray/tools/dispatcher.py` — `TOOLS` dict + arg-unpacking branch.
4. `src/kervansaray/tools/schemas.py` — JSON-schema declaration, Turkish
   description. For any optional param an LLM might over-fill, say so
   explicitly: *"SADECE kullanıcı X belirttiyse doldur"* — Nemotron
   hallucinates plausible-looking filter values otherwise (it did, twice).
5. `src/kervansaray/query_pipeline.py` — a `format_narrative` branch, and a
   `build_audit_metadata` entry (`surface` + `intent_map`) so the "Nasıl
   karar verdi?" panel doesn't show the generic fallback.
6. `src/kervansaray/llm/prompts.py` — a rule line + 1–2 few-shots. This is
   the single highest-leverage lever on routing accuracy in this codebase.
7. `tests/` — a new `test_tools_<name>.py`, plus update
   `tests/test_tool_schemas.py::test_function_declarations_complete`
   (hardcodes the tool count and name set).

If the new/changed tool result should show in the UI's result table
(`query_events`, `vehicle_history`), also add the column to `HEAD`/`ORDER`
in `index.html`'s `renderResult` and to the empty-column-hiding filter
already there (columns that are `null` on every row auto-hide, so it's safe
to add a column that's rarely populated).

Then the ship loop, then a live smoke-test with 2–3 phrasings including a
noisy one (ALL CAPS, extra punctuation, a synonym) — routing that works for
the few-shot's exact wording and fails on a paraphrase is the default
failure mode here, not the exception.

## New Flask route → Caddyfile

**This has broken a shipped feature three times.** `~/portfolio/Caddyfile`
does not blanket-proxy `/api/*` (deliberate — it would swallow the
portfolio's own `/api/stats`, `/api/guestbook`, etc.). Every new route under
`src/kervansaray/api/routes_*.py` needs an explicit block added to
`~/portfolio/Caddyfile`:
```
handle /api/<your-route>* {
    reverse_proxy kervansaray_app:8000
}
```
placed before the trailing `handle { reverse_proxy web:8000 }` fallback.
Without it the route works on `localhost:8000` (direct Flask, no Caddy) and
404s on the live domain — which is exactly why step 7 of the ship loop
("live smoke-test against localhost") **will not catch this class of bug**.
Test the live domain (`curl -s -o /dev/null -w '%{http_code}\n' https://yagizakkaya.com.tr/api/<route>`)
whenever you add a route, not just localhost.

After editing `~/portfolio/Caddyfile`, `caddy reload` reads a stale inode
(bind-mounted single file) — you must:
```bash
cd ~/portfolio && docker compose up -d --force-recreate caddy
```

## Migration checklist

`alembic/versions/0001_initial.py` builds the schema from the **live**
`Base.metadata` (`create_all`), not a frozen SQL snapshot — meaning every
column current models declare already exists after `0001` alone. A later
migration doing plain `op.add_column(...)` therefore fails with
`DuplicateColumn` on a from-scratch `alembic upgrade head` (this broke
`test_migrations::test_upgrade_downgrade_upgrade` twice). Always write
schema-changing migrations idempotently:
```python
op.execute("ALTER TABLE <table> ADD COLUMN IF NOT EXISTS <col> <type>")
...
op.execute("ALTER TABLE <table> DROP COLUMN IF EXISTS <col>")  # downgrade
```
`v_events` is a Postgres `VIEW` — Postgres cannot `ALTER` a column onto a
view, only `DROP`+`CREATE`. `src/kervansaray/db/views.py::V_EVENTS_SQL` is
the single source of truth for its definition (`db/views.py::rebuild_schema`
uses it for the test/eval path; `0001` imports it for the real migration
path). A migration that adds a view-visible column must:
```python
from kervansaray.db.views import V_EVENTS_SQL
...
op.execute("DROP VIEW IF EXISTS v_events")
op.execute(V_EVENTS_SQL)  # current definition, already includes the new column
```
and its `downgrade()` must inline a frozen copy of the *pre-change* view SQL
(you can't import "the old version" — copy it from the previous migration's
diff).

Verify a migration actually round-trips (the container test above runs
`pytest`, but `test_migrations` needs the real Alembic path, not
`rebuild_schema`):
```bash
docker compose exec -T db psql -U kervansaray -c "DROP DATABASE IF EXISTS ks_mig" >/dev/null
docker compose exec -T db psql -U kervansaray -c "CREATE DATABASE ks_mig" >/dev/null
docker run --rm --network kervansaray_default -v "$PWD":/w -w /w \
  -e DATABASE_URL="postgresql+psycopg://kervansaray:kervansaray@db:5432/ks_mig" \
  python:3.11-slim sh -c "pip -q install -e '.[dev]' >/dev/null 2>&1; alembic upgrade head && alembic downgrade base && alembic upgrade head"
```
Then apply for real on the live DB (bind-mounted `alembic/` so the running
`app` container already sees the new migration file):
```bash
docker compose exec -T app python -m alembic upgrade head
```
and re-seed if the migration touches demo data (`docker compose exec -T app python scripts/seed_demo.py`, then step 6 of the ship loop).

**Restart `app` after any migration that touches `v_events` (`DROP VIEW` +
`CREATE VIEW`) — not optional.** The running gunicorn workers hold a
connection pool with statement plans already prepared against the *old*
view/table shape (psycopg auto-prepares after a few identical-shaped
queries). A `DROP`+`CREATE` changes the relation's OID even when the
resulting columns are identical, and the next query on a poisoned pooled
connection throws `psycopg.errors.FeatureNotSupported: cached plan must not
change result type` — a live 500 on `/api/query` that persists until the
process restarts and gets fresh connections. `docker compose restart app`
(step 6 of the ship loop) clears this; running the migration without it does
not. Found via `tests/test_migrations.py` poisoning the *test* suite's
shared connection pool the same way — fixed there with `get_engine().dispose()`
in the migration fixture's teardown, which is the test-side analogue of the
container restart.

## Puppeteer live-verification

For a UI change, curl isn't enough — verify against the **live domain**
(`https://yagizakkaya.com.tr/urettiklerim.html`), not `localhost:8000`
directly: dark mode, Caddy routing, and SSE buffering only manifest through
the real path.

```bash
cd <scratchpad> && npm init -y >/dev/null 2>&1 && npm i puppeteer@23 >/dev/null 2>&1
```
Then a script that: seeds `localStorage['ks-theme']` via
`page.evaluateOnNewDocument` *before* `page.goto` (setting it after load
misses the anti-flash inline script in `<head>`), navigates, screenshots,
and asserts on both DOM state and `page.on('pageerror'|'response')` for
console errors / any 4xx-5xx. Check both themes and at minimum one action
that mutates shared state while a non-default tab/view is active (that
combination is where render races hide — see the sessions-tab bug: a
background `fetchRegistry()` call clobbered a `sessions`-tab table because
neither renderer checked which tab was active before writing to the shared
`<tbody>`).

## Turkish text gotchas

- **Accent-insensitive matching**: Postgres `ILIKE` is case-insensitive but
  not diacritic-insensitive (`'Güvenlik' ILIKE '%guvenlik%'` is false). Use
  the `unaccent` extension (`CREATE EXTENSION IF NOT EXISTS unaccent`,
  already installed by `alembic/versions/0003_*`): `unaccent(col) ILIKE
  unaccent(:term)`.
- **Python `.lower()` mangles Turkish İ**: `"İÇERİDE".lower()` produces
  `"i̇çeri̇de"` (a combining-dot codepoint), not `"içeride"`. When you need a
  Turkish-correct downcase (e.g. normalizing a shouted query before it hits
  the LLM), do `text.replace("İ", "i").replace("I", "ı").lower()` first.
