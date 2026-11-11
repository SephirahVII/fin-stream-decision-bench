# Anti-leak review — `equity-event-001`

**Verdict: LEAK FOUND**

| | |
|---|---|
| Repo | `<repo>` |
| Commit reviewed | `f7f4e00` (branch `main`; case and workflow are untracked at review time) |
| Case | `tasks/equity-event-001` (replay clock, Alphabet Q1 2026 earnings night) |
| Review date | 2026-11-11 |
| Method | static source review, independent recomputation of `available_at_s`, direct `DataService` probing, controller end-to-end probes, judge-script probes, raw workspace/DB scans |
| Repo modifications | none except this report; all test code is under `<workdir>/leak_audit` |

## 1. Executive summary

The **replay-clock data boundary itself holds**. All 30 filings, 6 documents, 20,777 XBRL facts, 718 prices, 4 consensus rows and 12 issuer events carry an `available_at_s` exactly equal to the true source publication time; the visibility matrix shows no Q1-2026 fact, 10-Q, 8-K exhibit, post-2026-04-29 price bar or post-shift peer filing during the shift. SQL and `read()` bypass attempts did not reach future rows.

The case nevertheless **leaks future information through the agent-visible workspace**, and it has two integrity defects that materially weaken the intended protection:

1. **Critical answer leak:** `desk/manual.md:33-34` uses the actual Q1 2026 judge-side values as formatting examples: `109896.0` (actual total revenue) and `36.12` (actual operating margin, truth `36.1214`). The manual is loaded into `public_files` at `controller.py:54-56`, is readable at t=0 via `read(path="desk/manual.md")` (`engine.py:113-118`), and was returned in 4,841 characters by the protocol probe. This exposes the total-revenue actual 3,695 s before the 8-K (and the forecast deadline is 3,300 s) and exposes a verification GAAP/margin answer before the 10-Q.
2. **High-severity crash:** a future-document read (or any forbidden query) raises `DataRejected` (`data_service.py:29`, `:147`, `:76-84`), but `controller.py:93` catches only `(Rejected, ValueError, TypeError)`. The episode dies with rc=1 and a traceback; the failed read is never journaled, so the `read_unpublished` penalty in `judge/verify_ingest.py:199-201` is unreachable in the real protocol.
3. **Audit is soft:** a submission can cite the 10-Q before release and still pass the aggregate: one future citation scores `audit_integrity=0.75`, weighted-with-rubric `0.975`; two future citations score `0.5` / `0.95` (all with rubric=1.0). `task.toml:96-103` sets `audit_integrity` weight 10 but `must_pass=false`. Citing a visible document without ever reading it scores audit `1.0` (`08_audit_unread.py`), so citations are not evidence of reading.

No raw-database future-row leak was found through the intended protocol. The verdict is **LEAK FOUND**, not “no leak”, because the manual is part of the agent surface and contains judge-answer values.

## 2. Test matrix

All commands were run from the repo root with the workspace DB at `tasks/equity-event-001/environment/initial_workspace/market.db`; scripts are in `<workdir>/leak_audit`.

| # | Command | Result |
|---|---|---|
| 1 | `python3 <workdir>/leak_audit/01_availability.py` | All rows exact: filings 30/30, filing_documents 6/6, xbrl_facts 20777/20777, prices 718/718, consensus 4/4, issuer_events 12/12; `early_leak=0`, `later_than_source=0`, `missing=0`. “PROBLEMS: none”. |
| 2 | `python3 <workdir>/leak_audit/02_visibility.py` | Matrix in §4.2: t=0/3599 → 3 docs, 17 filings, max price 2026-04-28, 0 Q1 facts; t=3695 → 5 docs incl. 8-K + EX-99.1; t=21731+ → 6 docs incl. 10-Q and 216 Q1 facts; max price never passes 2026-04-29; 0 future price rows at every tested t. |
| 3 | `python3 <workdir>/leak_audit/03_bypass.py` | All dangerous probes rejected (multi-statement, ATTACH/DETACH, PRAGMA, sqlite_master, writes, `load_extension`/`readfile`/`writefile`, `src.`, `filing_documents`, hidden tables, `dbstat`, `SELECT content`). **One bypass:** `sqlite_schema` is readable (9 rows, schema only; no future data). `read()`/`read(path)` traversal rejected. |
| 4 | `python3 <workdir>/leak_audit/04_search.py` | **LEAK:** `desk/manual.md` contains `109896` once and `36.12` once; t=0 protocol read returns both. `prompt.md` has no hits. Raw `market.db` has no `ground_truth`/`rubric`/`judge` strings. All answer tokens in DB content are at their legitimate release availability (3695/21731/90000); no token is visible in the three t=0 docs. |
| 5 | `python3 <workdir>/leak_audit/05_audit.py` | Perfect evidence 1.0 on all command checks. One future citation: audit 0.75, weighted 0.975, passes 0.95. Two: audit 0.5, weighted 0.95, passes. Unknown doc: 0.85/0.985. Future + failed-read journal: 0.5/0.95. Late forecast at 3301: total 0.6667, fails. `audit_integrity` CLI for two future citations: `outcome=fail, score=0.5`, but aggregate can still pass because `must_pass=false`. |
| 6 | `python3 <workdir>/leak_audit/06b_controller_clean.py` | rc=0, 12 agent/event messages, 3 submissions at `at_s` 50 / 3715 / 21751 (all before deadlines), 12 journal entries, pre-seeded forged `evidence/equity_event.json` overwritten. |
| 7 | `python3 <workdir>/leak_audit/06c_controller_crash.py`; `python3 <workdir>/leak_audit/06d_controller_crash_sql.py` | Future 10-Q read at t=0: rc=1; traceback `controller.py:91 → engine.py:119 → data_service.py:147 DataRejected: Document is not published at the current business time`; evidence written with `actions_used=1`, `journal=1`, empty submissions; failed read not journaled. Forbidden `PRAGMA` query: rc=1, traceback ending `data_service.py:80 DataRejected: Only read-only SELECT queries over published tables are allowed`. |
| 8 | `python3 <workdir>/leak_audit/07b_expensive.py` | 2-way XBRL cartesian `COUNT(*)` (393,189,241) completes in 2.0 s; 4-way and 5-way price cartesians are stopped by the progress handler with `SQL error: interrupted` after ~4.8 s. No unbounded query observed. |
| 9 | `python3 <workdir>/leak_audit/08_audit_unread.py` | Visible-doc citation with **no journal read**: `score_audit=1.0`; future citation no read: 0.75; future citation + failed read: 0.5. Confirms audit checks metadata only, not reading. |

## 3. Case facts used in this review

- Epoch `2026-04-29T19:00:00Z` (15:00 ET); shift end t=23,400 (21:30 ET); deadlines forecast 3,300, reconciliation 4,800, verification 22,800 (`judge/ground_truth.json:7`).
- 8-K accepted `2026-04-29T20:01:35Z` → t=3,695; 10-Q accepted `2026-04-30T01:02:11Z` → t=21,731; 2026-04-29 close at `2026-04-29T20:00:00Z` → t=3,600.
- Truth actuals (`judge/ground_truth.json:8-22`): total revenue 109,896.0; TAC 15,228.0; net revenue 94,668.0; diluted EPS 5.11; net income 62,578.0; operating income 39,696.0; operating margin 36.1214%; Google Services 89,637 / 40,589; Google Cloud 20,028 / 6,598.
- Consensus (`judge/ground_truth.json:23`): net revenue 91,690.0; diluted EPS 2.76. The prior consensus 91.69 / 2.76 is legitimately visible in `consensus_estimates` at t=0.
- Agent-visible workspace contains exactly `market.db` and `desk/manual.md`; no `judge/`, `data/`, `.git`, prompt, or fixtures.
- `market.db` sha256 matches `build_provenance.json` (`4ae6eb90…`), 3,616,768 bytes. Raw DB does contain future rows by design; only the protocol gate is intended to hide them.

## 4. Detailed results

### 4.1 Availability recomputation (`01_availability.py`)

Independent recomputation uses the source timestamps and the epoch `2026-04-29T19:00:00Z`, with `max(0, seconds since epoch)`.

| Table | Rows compared | Early leak | Later than source | Missing | Notes |
|---|---:|---:|---:|---:|---|
| `filings` | 30 | 0 | 0 | 0 | `accepted_at_utc`; includes peers |
| `filing_documents` | 6 | 0 | 0 | 0 | DB uses filing `accepted_at`; every document `published_at` equals that accepted time |
| `xbrl_facts` | 20,777 | 0 | 0 | 0 | accession is mapped through `filings.csv`; fallback is `filed_utc` |
| `prices` | 718 | 0 | 0 | 0 | `available_at_utc`; 20:00Z in EDT, 21:00Z after DST ends |
| `consensus_estimates` | 4 | 0 | 0 | 0 | `as_of_utc` = 2026-03-17T16:53:01Z |
| `issuer_events` | 12 | 0 | 0 | 0 | `accepted_at_utc` |

Additional checks:

- Q1-2026 `period_end=2026-03-31` facts: **216** from accession `0001652044-26-000048` at `available_at_s=21731`; **2** from accession `0001652044-26-000071` (filed 2026-07-23) at `7,280,154`. No Q1 fact is visible before 21,731.
- XBRL facts filed after 10-Q acceptance but visible during shift: **0**.
- Price bars after 2026-04-29: **135**; visible during shift: **0**. The 2026-04-30 close 384.80 is at 90,000.
- No row is materially late for solvability. The 8-K and 10-Q are exactly on the judge truth’s `available_at_s` (3,695 / 21,731).

Verdict on §4.1: **no availability leak, no missing/solvability break**.

### 4.2 Visibility matrix (`02_visibility.py`)

Direct `DataService` at the required times; `docs` is the number of visible document ids.

| t (business s) | Docs | Filings | Max visible trade date | Price rows | GOOGL 10-Q | Q1-2026 facts | Future price rows | Read probe |
|---:|---:|---:|---|---:|---:|---:|---:|---|
| 0 | 3 | 17 | 2026-04-28 | 582 | 0 | 0 | 0 | 8-K EX-99.1, 8-K primary, 10-Q → “not published” |
| 3,599 | 3 | 17 | 2026-04-28 | 582 | 0 | 0 | 0 | same |
| 3,600 | 3 | 17 | 2026-04-29 | 583 | 0 | 0 | 0 | same; 4/29 close now visible |
| 3,694 | 3 | 17 | 2026-04-29 | 583 | 0 | 0 | 0 | same |
| 3,695 | 5 | 18 | 2026-04-29 | 583 | 0 | 0 | 0 | 8-K EX-99.1 OK (23,561 chars); 8-K primary OK (5,225); 10-Q denied |
| 4,700 | 5 | 21 | 2026-04-29 | 583 | 0 | 0 | 0 | 10-Q denied |
| 21,730 | 5 | 24 | 2026-04-29 | 583 | 0 | 0 | 0 | 10-Q denied |
| 21,731 | 6 | 25 | 2026-04-29 | 583 | 1 | 216 | 0 | 10-Q OK (22,857 chars) |
| 22,800 | 6 | 25 | 2026-04-29 | 583 | 1 | 216 | 0 | 10-Q OK |
| 23,400 | 6 | 25 | 2026-04-29 | 583 | 1 | 216 | 0 | 10-Q OK |

Catalog row counts: at t=0 -> issuers 9, filings 17, documents 3, xbrl_facts 19,829, consensus 4, prices 582, issuer_events 6. At t=23,400 -> 9 / 25 / 6 / 20,235 / 4 / 583 / 11. No content column is exposed by `catalog()`.

Answer-cell scan across every visible table: no judge-answer token at t ≤ 3,695; at 21,731+ only one hit — the legitimate Q1 EPS 5.11 in `xbrl_facts`. `384.8` never appears.

Verdict on §4.2: **the temporal boundary holds for the intended protocol**.

### 4.3 Query and `read()` bypass probes (`03_bypass.py`)

Rejected:

- Multi-statement write; `ATTACH`/`DETACH`; `PRAGMA` (literal, `pragma_table_info`, `pragma_table_list`, `pragma_database_list`); `INSERT`/`UPDATE`/`DELETE`/`CREATE`/`DROP`/`ALTER`/`VACUUM`/`REPLACE`; `load_extension`, `readfile`, `writefile`.
- `sqlite_master` literal/quoted/bracketed/uppercase; `sqlite_temp_master`; `sqlite_temp_schema`; `sqlite_dbpage`; `dbstat`.
- `filing_documents`; `_hidden_stream_schedule`; `_hidden_manifest`; `SELECT content FROM documents`; `SELECT content FROM filing_documents`.
- `SELECT * FROM src.filings` (prefilter `src.`); `SELECT * FROM "src"."filings"` gives `SQL error: no such table: src.filings`, proving the source connection is detached before agent queries.

Allowed / false positives:

- `SELECT 'drop'` and `SELECT ';'` are rejected although semantically harmless; trailing semicolon is rejected by the one-statement rule. These are usability false positives, not leaks.
- `WITH x AS (SELECT 1) SELECT 1` works. `WITH RECURSIVE` with an arbitrary CTE name fails `SQL error: not authorized` because the authorizer sees `SQLITE_READ` on the CTE name; naming the CTE `prices` works (`prices` is in `EXPOSED`). Functional bug only.
- A 2-way cartesian `COUNT(*)` over `xbrl_facts` (393,189,241 rows) completes in ~2.0 s; 4-way/5-way price cartesians hit the progress handler and return `SQL error: interrupted` after ~4.8 s.

**Bypass found (low data risk):** `SELECT * FROM sqlite_schema` and quoted variants return 9 rows — the 7 in-memory published tables plus indexes `idx_docs_doc`, `idx_filings_fil`. Cause: `sqlite_schema` is absent from `FORBIDDEN` (`data_service.py:23-25`) while the authorizer allowlist adds `sqlite_master` (`data_service.py:86-87`) and allows any read with `arg1 == sqlite_master` (`:94-95`); the alias’s authorizer `arg1` is `sqlite_master`. The leak is schema-only:

- 9 rows, `sql` column contains `CREATE TABLE` DDL with columns, no data;
- `WHERE name LIKE '%hidden%'` returns 0;
- the in-memory schema has no `dbname` column in this SQLite build;
- `documents, sqlite_schema` join returns 54 rows (6 docs × 9), still no document content;
- source DB is detached; `"src"."filings"` is not accessible.

Latent risk: the authorizer ignores `dbname`. If the source ATTACH ever survives into `query()` (e.g. a future refactor or a failed detach), the prefilter only blocks the literal `src.`, and `"src"."filings"` would bypass that substring while the authorizer allows `filings`. Today it is not exploitable, but the defense relies entirely on `DETACH`.

`read()`: future 8-K/10-Q → exact `Document is not published at the current business time`; unknown ids, `x' OR '1'='1`, `../../etc/passwd`, `desk/manual.md`, `../judge/ground_truth.json` → `Unknown document id: …`; empty → `doc_id required`; 10-K returns 17,186 chars.

`Desk` read(path): `market.db`, `../judge/ground_truth.json`, `/etc/passwd`, `data/filings.csv` → `Unknown workspace file: …`; `desk/manual.md` OK; no args → `doc_id required`; 10-Q at t=0 denied; 10-K OK.

Verdict on §4.3: **no future-row leak found**; one schema-introspection control gap and one latent dbname issue.

### 4.4 Answer reachability and the manual leak (`04_search.py`)

- `desk/manual.md:33-34` contains:
  - `Reporting conventions: USD millions to 1 decimal for company figures (e.g. 109896.0), USD per share`
  - `for EPS (2 decimals), percentages in percentage points (e.g. 36.12). The desk's frozen sell-side`
- `109896.0` equals `judge/ground_truth.json:9` `total_revenue_usd_m`; `36.12` rounds `judge/ground_truth.json:15` `operating_margin_pct=36.1214` (judge margin tolerance 0.05, `ground_truth.json:36`).
- The manual is loaded by `controller.py:54-56` into `public_files`; `engine.py:113-118` serves `read(path=...)` from that dict. A direct `Desk` read at t=0 returned:
  - `ok: desk/manual.md chars: 4841 at_s: 10`
  - both leaked lines exactly as above.
- `prompt.md` has no answer-token hits. The workspace contains exactly `desk/manual.md` (4,855 bytes) and `market.db` (3,616,768 bytes).
- Raw `market.db` scan: no `ground_truth`, `rubric`, `expected_answer`, `judge`, or `answer_key` strings. Answer-bearing content exists only at legitimate availability: `filing_documents.content` at 3,695 / 21,731; `prices.close=384.8` at 90,000; `xbrl_facts` at 21,731.
- False positives explained: `xbrl_facts.value=15228000000` at t=0 is a 2023 available-for-sale securities value, not TAC; `prices.high=185.11` is a historical price, not EPS; an early regex hit on `36.1` matched a date fragment — the exact-string scan found only the manual as a t=0 leak.
- The 8-K EX-99.1 at t=3,695 legitimately contains 109,896 (×6), 94,668 (×1), 15,228 (×1), 5.11 (×3), 36.1 (×1), 62,578 (×3), 20,028 (×2), 40,589 (×2), 39,696 (×4). It is a public release at that time, not a temporal leak.

Verdict on §4.4: **leak confirmed via `desk/manual.md`; no raw-DB answer leak through the protocol**.

### 4.5 Audit-integrity gamiability (`05_audit.py`, `08_audit_unread.py`)

`judge/verify_ingest.py:173-207` scores citations against `truth['documents']` metadata and the submission’s true `at_s`:

- unknown/non-string citation: `+0.15` each;
- `available_at_s > at_s`: `+0.25` each;
- failed read with “not published” in reason: `+0.25`, capped at 0.5;
- failed submit: `+0.05`, capped at 0.2;
- no check that a cited document was actually read; no check of `basis`/`memo` content.

Measured, with rubric checks assumed 1.0 and weights from `ground_truth.json:52-54`:

| Evidence variant | `audit_integrity` | Weighted total | Pass ≥0.95 |
|---|---:|---:|---|
| Perfect | 1.00 | 1.000 | yes |
| One future 10-Q citation in forecast | 0.75 | 0.975 | **yes** |
| Two future 10-Q citations (forecast + reconciliation) | 0.50 | 0.950 | **yes** |
| Same, with a failed-read journal entry | 0.50 | 0.950 | **yes** |
| Unknown doc | 0.85 | 0.985 | yes |
| Late forecast at 3,301 | 1.00 | 0.667 | no |
| Visible 10-K citation, no read at all | 1.00 | 1.000 | yes |

A one-future-citation submission passes if the two rubric checks average ≥0.833; two future citations need a perfect 15/15 rubric. The standalone `audit_integrity` check returns `outcome=fail, score=0.5` for the two-citation case, but `task.toml:96-103` has `weight=10` and `must_pass=false`, so the aggregate can still pass at 0.95. `task.toml:32-33` confirms `method="weighted_mean"`, `pass_threshold=0.95`; the repo does not include the aggregator implementation, so this is inferred from the declared weights.

Verdict on §4.5: **a future citation can pass the aggregate; citations are not proof of reading** — needs hardening even though the temporal gate is intact.

### 4.6 Controller end-to-end and failure behavior (`06b`, `06c`)

Clean path: 12 actions, rc=0, 12 journal entries, submissions at `at_s` 50 / 3,715 / 21,751 (all before deadlines), events at 3,600 / 3,695 / 21,731, pre-seeded forged `evidence/equity_event.json` overwritten by `controller.export()`. The `write` action is rejected by `Desk.act` as unknown; the agent has no file-write tool.

Failure path: at t=0, `read(doc_id="googl-10q-20260331")` after the manual read produces:

```
controller.py:91  value = desk.act(action)
engine.py:119     return self.data.read(action.get('doc_id'))
data_service.py:147  raise DataRejected('Document is not published at the current business time')
data_service.DataRejected: Document is not published at the current business time
```

rc=1, no `tool_result`; `evidence/equity_event.json` exists with `actions_used=1`, `journal=[manual read]`, empty submissions. The failed future read is not journaled, so the audit’s read_unpublished penalty cannot fire. The same crash occurs for forbidden SQL (e.g. `PRAGMA table_info(issuers)`), because `DataService.query` raises `DataRejected` at `:76-84` and `controller.py:93` does not catch it.

## 5. Findings

### F1 — Critical: actual Q1 values in the agent-visible manual

**Evidence**

- `tasks/equity-event-001/environment/initial_workspace/desk/manual.md:33` — `109896.0`; `:34` — `36.12`.
- `judge/ground_truth.json:9` — `total_revenue_usd_m: 109896.0`; `:15` — `operating_margin_pct: 36.1214`; `:36` — `margin_tol_pct: 0.05`.
- `controller.py:54-56` loads the manual into `public_files`; `engine.py:113-118` returns it for `read(path="desk/manual.md")`; the protocol read at t=0 returned 4,841 chars including both lines.
- `04_search.py` exact-string scan: `desk/manual.md [('109896', 1), ('36.12', 1)]`; `prompt.md NONE`.

**Impact**

- Total revenue actual is available at t=0, 3,695 s before the 8-K and 3,300 s before the forecast deadline. With a TAC estimate near 15,000, net revenue is `109,896 - 15,000 = 94,896`, inside the 1,420.02 forecast tolerance; the leaked value alone converts the forecast from extrapolation into arithmetic.
- Operating margin is a scored verification item (`tenq_verification`, 15 points); total revenue is a scored reconciliation item (20 points) and forecast input. The actual 8-K publishes the same values at 3,695, so the leak is “early” rather than “never public”, but it contaminates the forecast window and all pre-8-K analysis.
- The manual is not a citable `doc_id`, so `audit_integrity` cannot attribute the value and does not penalize it. The agent can use the leaked number and cite an unrelated visible doc; audit stays 1.0.

**Fix**

- Replace both examples with values that are not judge answers (e.g. `123456.7`, `12.34`) or use placeholders. Do not use any row from `ground_truth.json` or `o19_ground_truth.json`.
- Add a build/CI assertion that scans `desk/manual.md`, `prompt.md`, and every workspace file for all truth/o19 values, allowing only legitimate prior-public values (91.69, 2.76, historical 2025 figures).
- Regenerate/verify the workspace and rerun the anti-leak checklist.

### F2 — High: `DataRejected` crashes the controller and suppresses the audit journal

**Evidence**

- `data_service.py:29` `class DataRejected(Exception)`; raises at `:76`, `:80`, `:82`, `:84`, `:144`, `:147`.
- `controller.py:93` `except (Rejected, ValueError, TypeError) as exc` — `DataRejected` is not caught.
- `engine.py:112-119` routes document reads through `data.read`; `engine.py:108-109` routes SQL through `data.query`.
- Reproduced traceback: `DataRejected: Document is not published at the current business time`; rc=1; evidence `actions_used=1`, `journal=1`, empty submissions.
- Reproduced forbidden-query variant (`PRAGMA table_info(issuers)`): rc=1, traceback ending `data_service.py:80 DataRejected: Only read-only SELECT queries over published tables are allowed`.

**Impact**

- Any model that probes a future document or a forbidden query (a natural action) loses the entire episode and scores zero on all phases. This is a severe reliability/UX and calibration bug; it also makes `verify_ingest.py:199-201` dead code for the real protocol.
- It creates a perverse incentive: avoid legitimate exploration, since a mismatch between presumed and actual availability is fatal.

**Fix**

- Import/catch `DataRejected` in `controller.py` (or make it a subclass of `Rejected`) and return `{ok: false, reason: ...}`.
- Record the failed read/query in the journal with the true `at_s` so the audit penalty works; keep the run alive.
- Add a regression test for future-doc read, forbidden query, and invalid submit.

### F3 — Medium/High: audit allows future citations and unread citations

**Evidence**

- `task.toml:96-103`: `audit_integrity` weight 10, `must_pass = false`; `task.toml:32-33` weighted mean, threshold 0.95.
- `verify_ingest.py:38-45` `pick_submission` selects `at_s <= deadline`; `:173-207` only checks citation metadata, never journal reads.
- Measured: one future citation -> audit 0.75, weighted 0.975; two -> 0.5, 0.95; visible but unread citation -> 1.0. Standalone audit check fails (0.5) but aggregate passes because `must_pass=false`.

**Impact**

- A model can cite the 10-Q at forecast time and still pass the aggregate if its rubric scores are strong. It can also fabricate citations to visible documents without reading them; the audit treats that as fully compliant.
- The audit’s design intent (“journal doc availability check”) is not enforced in the real protocol because the controller crash prevents failed-read journaling (F2), and even a journaled failed read only costs 0.25.

**Fix**

- Set `audit_integrity` `must_pass = true` (and/or zero the phase/aggregate on any `available_at_s > at_s` citation).
- Require each cited `doc_id` to appear in a successful `read` journal entry at or before the submission’s `at_s`; penalize unread citations.
- Keep the failed-read journal path alive (F2).
- Consider a post-submission consistency check of `basis`/`memo` claims against cited docs.

### F4 — Low: `sqlite_schema` alias bypasses the `sqlite_master` block

**Evidence**

- `data_service.py:23-25` `FORBIDDEN` has `sqlite_master` but not `sqlite_schema`.
- `data_service.py:86-87` allowlist adds `sqlite_master`; `:94-95` allows any `SQLITE_READ` with `arg1` in that set.
- `SELECT * FROM sqlite_schema` returns 9 rows (7 in-memory tables + 2 indexes); `documents, sqlite_schema` join returns 54; quoted and subquery forms work.
- Source DB is detached: `"src"."filings"` -> `no such table: src.filings`; `SELECT * FROM src.filings` blocked by prefilter.

**Impact**

- No future rows/content are reachable; scope is the in-memory published schema (table names, columns, index names). This defeats the apparent “no schema introspection” control and could help query construction, but is not an answer leak.
- Latent: the authorizer ignores `dbname`; the prefilter only blocks `src.`. If the source attach ever survives into `query()`, `"src"."filings"` would slip past both; the current safety relies on `DETACH`.

**Fix**

- Add `sqlite_schema`, `sqlite_temp_schema`, `sqlite_temp_master` to `FORBIDDEN`, or remove `sqlite_master` from the allowlist and test whether SQLite still compiles ordinary queries; alternatively deny `SQLITE_READ` unless `dbname == 'main'`.
- Add a test that `sqlite_schema` is not readable, and that `"src"."filings"` fails even if source is hypothetically attached.

### F5 — Informational: the 8-K exhibit already contains 9/10 verification values

At t=3,695 the EX-99.1 includes total revenue, TAC, net revenue, EPS, operating income, operating margin, net income, segment revenue, segment operating income and segment margins. Only `consistency.press_release_matches_10q` needs the 10-Q. This is public-release redundancy, not a temporal leak; it does mean `tenq_verification` can be largely completed before 21,731 and the 10-Q is only needed for one item. If the design intends the 10-Q to be the unique verification source, move segment/GAAP detail to the 10-Q or require a 10-Q citation for those items.

### F6 — Informational: forecast is difficult without the leaked total revenue

Consensus net revenue 91.69 vs actual 94.668 is a +3.2479% beat; forecast tolerance is 1,420.02 USD m (1.5% of actual). Consensus-as-forecast scores 0. At the 3,300 deadline the 8-K (3,695) is not yet public, so a legitimate forecast must extrapolate total revenue and TAC from history/consensus. The manual leak (F1) removes most of that difficulty. This is a calibration/solvability concern, not a temporal leak. Also, `wait` to a deadline then `submit` costs 10 s and becomes late (manual says “before” the deadline); that is a minor UX trap.

### F7 — Low: query filter false positives and recursive CTE failure

- `SELECT 'drop'`, `SELECT ';'`, and any trailing semicolon are rejected by substring/one-statement checks (`data_service.py:79-84`), although harmless.
- `WITH RECURSIVE` with an arbitrary CTE name fails `SQL error: not authorized` because the authorizer sees `SQLITE_READ` on the CTE name (`:94-95`); naming the CTE `prices` succeeds. This is a functional limitation, not a security hole. Use a tokenizer/parser for write-keyword detection and allow CTE names explicitly if recursive queries are intended.

### F8 — Informational: design/doc discrepancies

The design doc claims hidden tables `_hidden_stream_schedule` and `_hidden_manifest`; the build script creates none (and `03_bypass.py` confirms they are unknown, not merely denied). Other discrepancies: design segment margin tolerance ±0.1pp vs `margin_tol_pct=0.05`; design says XBRL values REAL while the DB stores TEXT; design consensus snapshot 2026-03-24 vs data 2026-03-17; design references `scripts/build_equity_event_db.py` vs actual `tasks/equity-event-001/build_equity_event_db.py`; design peer docs ≥5 vs only 6 GOOGL docs; design DB 10–40 MB vs 3.6 MB; design budget 160 vs fixture 120. These do not leak future data but make the anti-leak/design claims inaccurate.

## 6. Residual risks

1. **Model pretraining knowledge.** The real Alphabet Q1 2026 results (published April 2026) may be in the model’s training data. The protocol cannot erase this; a model can output 109,896 / 5.11 from memory without reading anything. The case’s design acknowledges this (`design §13`), but the manual leak (F1) makes it worse and complicates attribution. Mitigation: use a less-memorable event, perturb/restate values, and score the in-window retrieval/update path explicitly.
2. **Raw `market.db` contains future rows.** The DB physically includes 10-Q content, Q1 facts and 2026-04-30 prices. The protocol gates them, but any harness or process with filesystem access (shell, `readfile`, a future tool) can read the raw file; `DataService` is the only barrier. The current `community.json-action` harness does not expose shell, but harness composition is part of the threat model. Mitigation: materialize a per-clock DB into the workspace, encrypt/split future rows, or keep the full DB judge-side.
3. **Evidence forgery outside the controller.** The controller overwrites a pre-seeded forged `evidence/equity_event.json` (`06b`), and `json_action/agent.py` has no file-write path to evidence. A shell-capable harness could still write after the controller exits or intercept the evidence path. Mitigation: write evidence to a controller-owned temp path with restrictive permissions and verify a controller signature/hash.
4. **Audit is not a hard gate.** As measured, one/two future citations can pass the aggregate (F3); an unread visible citation scores 1.0. The repo lacks the `weighted_mean` implementation, so the exact evaluator behavior is inferred; if the real aggregator differs, re-check. Mitigation: `must_pass=true` and read-journal enforcement.
5. **Controller crash on normal probing (F2).** A model that tests availability can lose the episode; this is both a reliability and a calibration risk. Fix before collecting benchmark numbers.
6. **8-K/10-Q redundancy (F5)** reduces the unique value of the 10-Q; forecast difficulty (F6) may produce low scores unrelated to leakage. Calibrate after fixing F1/F2/F3.
7. **`randomblob`/`zeroblob` are allowed** because all SQLite functions are allowlisted (`data_service.py:92-93`). A single large `randomblob` call can allocate memory before the progress handler runs; not tested to OOM, but a DoS surface. Consider denying memory-heavy functions or capping result size.
8. **Schema introspection (F4)** is low risk today, but the `dbname`-blind authorizer plus `src.`-only prefilter is a fragile combination if the attach/detach lifecycle changes.

## 7. Conclusion and required fixes

**Verdict: LEAK FOUND.** The DB’s temporal boundary is well constructed and survives every direct test: all `available_at_s` values are exact, post-shift rows never appear, and query/read bypasses do not reach future data. But the agent-visible `desk/manual.md` contains two judge-answer values at t=0, which is a real future-information leak on the agent surface and directly affects the forecast and verification scoring. The controller crash and soft audit are additional integrity defects that should block release.

Required before calling the case leak-free:

1. Remove the actual values from `desk/manual.md`; add the workspace truth-token scan to CI (F1).
2. Catch `DataRejected` and journal failed reads/queries (F2).
3. Make `audit_integrity` a hard gate and require read evidence for citations (F3).
4. Block `sqlite_schema` and add a `dbname == 'main'` authorizer check (F4).
5. Re-run `01`–`08` after the fixes; the expected result is then **NO LEAK FOUND** on the temporal boundary plus a clean manual scan.

## 8. Reproduction

Scripts (all under `<workdir>/leak_audit`):

| Script | Purpose |
|---|---|
| `01_availability.py` | Recompute `available_at_s` from source CSVs; leak/late/missing report |
| `02_visibility.py` | Direct `DataService` matrix and answer-cell scan |
| `03_bypass.py` | SQL/read/catalog bypass suite |
| `04_search.py` | Manual/prompt/raw-DB answer-token scan and t=0 protocol read |
| `05_audit.py` | Judge audit scoring on crafted evidence variants |
| `06b_controller_clean.py` | Clean controller E2E, forged-evidence overwrite |
| `06c_controller_crash.py` | Future-doc read crash reproduction |
| `06d_controller_crash_sql.py` | Forbidden-query crash reproduction |
| `07b_expensive.py` | Cartesian query/progress-handler test |
| `08_audit_unread.py` | Unread/future citation audit behavior |

Commands:

```bash
cd <repo>
python3 <workdir>/leak_audit/01_availability.py
python3 <workdir>/leak_audit/02_visibility.py
python3 <workdir>/leak_audit/03_bypass.py
python3 <workdir>/leak_audit/04_search.py
python3 <workdir>/leak_audit/05_audit.py
python3 <workdir>/leak_audit/06b_controller_clean.py
python3 <workdir>/leak_audit/06c_controller_crash.py
python3 <workdir>/leak_audit/06d_controller_crash_sql.py
python3 <workdir>/leak_audit/07b_expensive.py
python3 <workdir>/leak_audit/08_audit_unread.py
```

Key artifacts: `<workdir>/leak_audit/02_visibility.json`, `<workdir>/leak_audit/03_bypass.json`, and the controller workspaces `<workdir>/leak_audit/ctrl_clean` and `<workdir>/leak_audit/ctrl_crash2`.
