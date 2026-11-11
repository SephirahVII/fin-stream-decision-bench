# Realism review — `tasks/equity-event-001`

- **Date:** 2026-11-11
- **Reviewer:** independent validation subagent
- **Scope:** realism and internal consistency (not difficulty/solvability)
- **Verdict: FAIL**

The real-world timeline and the accounting arithmetic are strong. The case nevertheless fails
realism for three reasons that are independent of model capability:

1. the deterministic forecast checks make the documented, realistic pre-release path
   mathematically unable to reach the pass threshold;
2. the agent-facing manual leaks two exact post-release actuals before the 8-K;
3. the manual asks for a 10-Q verification of segment margins that the supplied 10-Q does not
   contain.

There are also material gaps between the design document and the implementation, and the
provenance package is incomplete. Details, with file:line evidence and commands, follow.

---

## 1. Blockers

### B1 — The intended pre-release forecast cannot pass the deterministic checks

**Evidence**

- `tasks/equity-event-001/task.toml:33` sets `pass_threshold = 0.95`; `:42` gives
  `forecast_revenue` weight 12; `:52` gives `forecast_eps` weight 8.
- `tasks/equity-event-001/judge/verify_ingest.py:56-63` scores
  `forecast.net_revenue_usd_m` linearly against the **post-release actual** `94,668.0`
  with tolerance `1,420.02`.
- `tasks/equity-event-001/judge/verify_ingest.py:66-73` scores
  `forecast.diluted_eps_usd` against the **post-release actual** `5.11` with tolerance `0.30`.
- `tasks/equity-event-001/judge/ground_truth.json:28-29` records those two tolerances.
- `docs/design/equity-event-stream-case-design.md:300` states the reference forecast is
  `91,690` (consensus) minus estimated TAC, "`≈ 82,500–83,000`", and says the case is scored
  mainly on method/probability, with a wide tolerance, and "不会因为'没猜中 +3.25% beat'而全盘失败"
  (will not fail completely for not hitting the +3.25% beat).
- `tasks/equity-event-001/environment/initial_workspace/desk/manual.md:26` labels the phase
  "pre-release forecast"; the 8-K does not arrive until t=3695, while the forecast deadline is
  t=3300 (`workflow-fixtures/scenario.json:8,12-14`).

**Arithmetic**

- Actual net revenue = `109,896 − 15,228 = 94,668`; feed tolerance is `1,420.02`.
  A forecast scores >0 only in `[93,248, 96,088]`, and needs to be very close to `94,668`
  to score materially.
- Consensus net revenue is `91,690` (`data/consensus.csv:2`; `judge/ground_truth.json:23`).
  Error `2,978` is `2.10×` tolerance, so the **consensus-anchored forecast scores 0.0**.
- The design reference `82,500–83,000` is even farther away (error `≈ 11,900`), also `0.0`.
- Actual diluted EPS is `5.11`; consensus is `2.76`; error `2.35` is `7.8×` the `0.30`
  tolerance, so the **consensus EPS forecast scores 0.0**.
- With both forecast checks at zero, the maximum possible weighted score is
  `100 − 12 − 8 = 80`, i.e. `0.80`, below `0.95`.

**Reproduction**

I built a submission with a consensus-anchored forecast and perfect reconciliation,
verification, probabilities, timeliness and audit, then ran the real judge:

```text
forecast_revenue       0.0   fail
forecast_eps           0.0   fail
probabilities          1.0   pass
reconciliation_actuals 1.0   pass
tenq_verification      1.0   pass
timeliness             1.0   pass
audit_integrity        1.0   pass
weighted total         0.80  < 0.95
```

Command used (one invocation per check):

```bash
cd tasks/equity-event-001
python3 judge/verify_ingest.py \
  --scenario judge/ground_truth.json \
  --submission <workdir>/equity-verify \
  --result <workdir>/equity-verify/forecast_revenue.json \
  --check forecast_revenue
```

The same result follows for the design's `82,500–83,000` reference. The claim in
`design:300` that a realistic forecast will not be "全盘失败" is false under
`verify_ingest.py:56-73` and `task.toml:33`.

**Impact:** The case rewards hindsight or foreknowledge, not pre-release analysis. Either the
forecast checks need a genuinely pre-release band (or an LLM/method score), or the case
cannot claim the documented reference path as realistic.

---

### B2 — The manual leaks exact post-release actuals before the 8-K

**Evidence**

- `tasks/equity-event-001/environment/initial_workspace/desk/manual.md:33-34` gives formatting
  examples:
  - `109896.0` — exactly actual total revenue (`judge/ground_truth.json:9`;
    `data/docs/000043_ex99_1.txt:26`);
  - `36.12` — actual operating margin rounded (`judge/ground_truth.json:15`;
    `data/docs/000043_ex99_1.txt:15` says 36.1%).
- The manual is the first tool an agent is told to read (`prompt.md:6-7`), so these values are
  visible at t=0, before the 8-K.
- The design's own anti-leak test 7 says the scan must confirm
  "无 future-only 数值泄漏到 manual/prompt（manual 只含 schema/规则）"
  (`docs/design/equity-event-stream-case-design.md:370`). The manual contains two future-only
  actuals, so test 7 would fail if actually run.

**Impact:** Even though the manual does not leak net revenue or EPS directly, it leaks total
revenue and operating income (from `36.12% × 109,896`). This weakens the forecast and violates
the stated anti-leak design. The examples should use placeholders (e.g. `123456.7`) or real
pre-shift figures, not the answer.

---

### B3 — The requested "10-Q verification of segment margins" is not supported by the 10-Q

**Evidence**

- `tasks/equity-event-001/environment/initial_workspace/desk/manual.md:28` requires
  "Form 10-Q verification of the release figures and segment margins".
- `manual.md:71-78` requires `segment_margins_pct` for Google Services and Google Cloud.
- `docs/design/equity-event-stream-case-design.md:303` says to read the 10-Q and verify
  "分部门利润率" (segment margins).
- The supplied 10-Q contains only segment **revenue**:
  `data/docs/000048_primary.txt:290-291` (Google Services 89,637; Google Cloud 20,028) and
  `:331-332` (same table).
- `grep -n '40,589\|6,598' data/docs/000048_primary.txt` returns **no matches**. The segment
  operating income figures `40,589` and `6,598` occur only in the press release:
  `data/docs/000043_ex99_1.txt:60-61` and `:213-214`.
- `data/EXTRACTION_REPORT.md:155` confirms the 10-Q text contains only selected key sections;
  no segment operating-income section is present.

**Impact:** A real analyst cannot verify the requested segment margins from the named filing.
The values can be copied from EX-99.1 into the verification payload and still score, but the
manual's stated source and the task premise are false. Either add segment operating income to
the 10-Q text or change the manual/design to say segment margins are verified from
EX-99.1 and only the GAAP totals from the 10-Q.

---

## 2. Major findings

### M1 — Manual/engine schema is not the design/rubric schema

`docs/design/equity-event-stream-case-design.md:242,255,266-268` requires:

- forecast `basis` objects with `{claim, source_doc_id, locator}` and a `method`;
- reconciliation `consensus.total_revenue_usd_m` and `notes`;
- verification `consistency.exceptions` and `memo`;
- `as_of_business_s` on each payload.

The agent-facing manual (`desk/manual.md:52-55,60-68,71-78`) and
`workflows/equity-event-stream/engine.py:198-262` instead specify:

- forecast `basis` as a list of free-text strings, no `source_doc_id`/`locator`/`method`;
- reconciliation `consensus.net_revenue_usd_m`, no `notes`;
- verification no `exceptions` or `memo`;
- no `as_of_business_s`.

The LLM rubrics require the missing material:

- `judge/rubric_evidence.json:11` asks for at least two data points "with locators";
  `:15` asks the verification to name the GAAP line and state the match.
- `judge/rubric_logic.json:15` asks for a concrete cross-check or caveat.

`engine.py` accepts extra fields, so a model that guesses the design schema can pass; but a
model following the authoritative manual has nowhere documented to put locators, the memo,
exceptions, or notes. This makes `evidence_chain` and `analysis_logic` unnecessarily
ambiguous.

**Impact:** major; evidence/logic scoring is not grounded in the documented agent surface.

### M2 — Database scale targets in the design are substantially unmet

`docs/design/equity-event-stream-case-design.md:180-186` targets:

| Target | Design | Actual |
|---|---|---|
| GOOGL XBRL facts | ≥8,000 | 20,777 (pass) |
| Peer filings/events | ≥200 | 25 peer filings / 12 `issuer_events` (fail) |
| Peer documents | ≥5 | 0 (fail) |
| Prices | GOOGL + 4–6 peers, 1 year | GOOGL only, 718 rows (fail) |
| Document bodies | ≥6 | 6 GOOGL docs (pass) |
| Total size | 10–40 MB | 4.3 MB data + 3.6 MB DB ≈ 7.9 MB (fail) |

The DB has 9 issuers and 30 filings, but peer `filing_documents` is empty and `prices`
contains only GOOGL. Relative-value or peer-news analysis — a core desk activity — is not
possible with the fixture as built.

**Impact:** major; the "full multi-issuer database" claim in the design is not what the
environment provides.

### M3 — Provenance manifest is incomplete; raw files and extraction scripts are absent

`tasks/equity-event-001/data/EXTRACTION_MANIFEST.json` lists 47 files:

- 14 `data/` entries: present, all `sha256` match; **all 14 lack `source_url`**.
- 28 `raw/` entries: have `source_url`, but the `raw/` directory is **absent** from the package.
- 3 `scripts/` and 2 internal entries: **absent**.
- `total_bytes` is `14,357,415`, but the present data is `4,325,168` bytes; the total includes
  missing raw/scripts.

`data/EXTRACTION_REPORT.md:7` says every file is listed with sha256/size; `:124` refers to
`manifest.json` (the file is `EXTRACTION_MANIFEST.json`); `:149` cites a `scripts/dl.py` log
that is not present; `:150-151` describes raw mirrors that are not in the package.

What is verifiable is good: `build_provenance.json` hashes match all 10 checked data files and
`market.db` (`db_sha256` and `db_bytes` match), and the data/doc values are consistent with the
filings. But the package cannot reproduce the raw-to-clean extraction, and the data entries
themselves have no source URLs.

**Impact:** major; "real public data" is plausible and numerically supported, but the
provenance chain is not self-contained.

### M4 — Design's consensus basis and reference forecast are internally contradictory

- `docs/design/equity-event-stream-case-design.md:69` calls the benchmark
  "Q1'26 总营收 $91.69B" (total revenue).
- `data/consensus.csv:2` says "revenue net of TAC" and `judge/ground_truth.json:23` is
  `net_revenue_usd_m: 91690.0`; `manual.md:69` says net-revenue basis.
- `design:300` then subtracts estimated TAC from `91,690` and calls the result net revenue.
  If `91,690` is already net, that double-counts TAC; if it is total, the reference should be
  about `77,700`, not `82,500–83,000`. The `82,500–83,000` figure implies a TAC ratio near
  9.8%, inconsistent with the 2025 ratio `13,748 / 90,234 = 15.2%`.
- `design:431` says the consensus was corrected to net revenue, but `:69` and `:300` still say
  total/consensus-total. The design is not internally consistent even after its own correction
  note.

**Impact:** major; the design's reference path and arithmetic are wrong, and this is the same
path that produces B1.

### M5 — Rubric/implementation details do not match the design

- Reconciliation: `design:317` says four actuals at 5 points each plus surprises/beat, which
  sums to 30 within a 20-weighted check. `verify_ingest.py:91-119` uses 3 points per actual
  (12 total), 2 per surprise (4), and 2 per beat (4), maximum 20.
- Segment tolerance: `design:318` says Services/Cloud margins tolerance `±0.1pp`;
  `verify_ingest.py:150-155` uses the single `margin_tol_pct = 0.05` for all three margins.
- Rubric files: `design:325` names `judge/rubric.json` and `judge/README.md`; the package has
  `judge/rubric_evidence.json` and `judge/rubric_logic.json`, and no `judge/README.md`.
- `design:336-347` specifies E1–E4 with weight 2 each; the actual rubric files use weight 1
  and different criteria text.
- `design:310` says every check carries `submission_paths`; only the two `llm_rubric` checks
  in `task.toml:105-120` do.

**Impact:** major; the published scoring documentation does not describe the shipped judge.

### M6 — README and dataset metadata are stale and contradict the case

- `README.md:59` says "判分不使用 LLM Judge：所有检查为确定性程序" (no LLM judge), but
  `task.toml:105-120` defines two `llm_rubric` checks (`evidence_chain` 8,
  `analysis_logic` 7).
- `README.md:47` says 7 cases; the repo now has 5 `task.toml` files.
- `README.md:49` says "三个 Workflow 控制器"; the repo has 4 harnesses
  (`workflows/*/harness.toml`).
- `dataset.toml:6` describes only LDI/treasury/source cases; `:12` keeps the default
  `judge_timeout_seconds = 30` while this task overrides 180.

`dataset.toml:8` uses `include = ["tasks/*/task*.toml"]`, so the new case is picked up despite
the stale prose.

**Impact:** major for the LLM-judge contradiction; minor for counts/description.

### M7 — Calibration and anti-leak evidence claimed by the design are absent

- `design:362-370` says the anti-leak test list is run and recorded in `docs/calibration/`.
- `design:372-381` requires 3 rollouts ≤40% and
  `docs/calibration/equity-event-001-CALIBRATION.md`.
- `find docs/calibration -maxdepth 1 -type f` returns only `source-treasury-ANALYSIS.md` and
  `source-treasury-CALIBRATION.md`. There is no equity-event calibration or anti-leak report.
- `design:419` claims an "independent validator 295 项断言 0 错误"; no such validator or report
  exists in the repo.
- `design:429` claims "确定性 checks 全部 1.0"; the consensus forecast and the design reference
  both score 0 under the shipped judge (B1).

**Impact:** major; the implementation-status section overstates verification.

### M8 — Judge-side post-event truth sits outside `judge/`

`tasks/equity-event-001/data/o19_ground_truth.json` has `judge_side_only: true` and contains
`q1_2026_rev_net_tac = 94.67` with `public_available_at = 2026-06-19T13:00:05Z` — after the
event. `design:356` says judge/ground-truth/rubric resources are in `judge/` and the
environment workspace contains none. The file is not in `initial_workspace` and is not in the
DB, so there is no live leak through the controller; but the stated packaging boundary is
wrong. If a future task pipeline materialises all of `data/` into the agent environment, the
answer is exposed.

**Impact:** major boundary/process risk; not an observed agent-visible leak today.

### M9 — Audit covers `source_doc_ids`, not the forecast's evidence

`judge/verify_ingest.py:173-207` audits only `payload.source_doc_ids`. The forecast schema
(`manual.md:52-55`) has no `source_doc_ids`; its `basis` is a free-text list. Therefore the
forecast's citations are not checked for existence, publication time, or whether the agent
actually read them. `design:320,358` claims the journal and doc-id audit cover the evidence
chain more broadly than they do.

**Impact:** major for the evidence-chain criterion; the deterministic audit does not cover the
phase where future information would be most damaging.

---

## 3. Minor findings

1. **Action budget inconsistency:** `design:203` says 160 actions; prompt (`prompt.md:8`),
   manual (`manual.md:9`) and fixture (`scenario.json:7`) say 120; `engine.py:28` defaults to
   160 but the fixture overrides to 120.
2. **Consensus date label:** `design:69` calls 2026-03-24 the consensus snapshot; the data
   `as_of_utc` is 2026-03-17T16:53:01Z (`data/consensus.csv:2`), and the extraction cutoff is
   3/24. The 3/24 label is defensible as a freeze time but is not the estimate's as-of date.
3. **Hidden tables:** `design:151` lists `_hidden_stream_schedule` and `_hidden_manifest`;
   `market.db` has no `_hidden_*` tables. The full future rows live in the normal tables and
   are gated by `DataService`, not physically segregated.
4. **"All peer data at 0" claim:** `design:160` says all peer data is visible at t=0. Actual
   peer 8-Ks are at 3811 (MSFT), 3941 (META), 4735 (AMZN); the 4/29 close is at 3600; the
   10-K/prior 8-Ks are at 0. The claim is false.
5. **Consensus unit trap:** `data/consensus.csv:2` stores `91.69` in `USD billions`, while
   `manual.md:33-35` says company figures are USD millions. The manual says the benchmark is
   net-revenue based but does not explicitly say "multiply by 1,000". A model can recover from
   the `unit` column, but the conversion should be explicit.
6. **Controller cwd / prompt wiring:** `workflows/equity-event-stream/controller.py:51-59`
   hardcodes `Path('desk/manual.md')` and `Path('market.db')` and ignores
   `setup['task']['input_files']`; `:81-82` sends no `prompt`/`input_files`, while
   `harnesses/json_action/agent.py:58` expects both on the first turn. The other controllers
   use `setup['task']['input_files']` and have the same send shape, so this may be a platform
   convention, but the equity controller is the only one that does not read the file list.
7. **`DataService` truncation flag:** `data_service.py` sets `truncated = len(result) >= 100`,
   so exactly 100 rows is flagged even when no more rows exist. Cosmetic.
8. **4/29 close wording:** `data/EXTRACTION_REPORT.md:65` calls the 20:00Z close
   "legitimately pre-shift"; it is 16:00 ET, i.e. pre-8-K but inside the shift. The value and
   `available_at_s = 3600` are correct; only the label is wrong.
9. **`EXTRACTION_REPORT` file names:** `:7` and `:124` say `manifest.json`; the file is
   `EXTRACTION_MANIFEST.json`. ``:149`` cites `scripts/dl.py`; no scripts directory exists.
10. **`build_equity_event_db.py` comment:** `:158` says "no post-event facts", but the XBRL
    CSV contains 542 rows filed after the event (269 at 2026-07-23, 273 at 2026-10-29),
    hidden by `available_at_s`. `EXTRACTION_REPORT.md:73` makes the same over-broad claim.
11. **Services margin precision:** `judge/ground_truth.json:20` is `45.2817`; exact
    `40,589 / 89,637 × 100 = 45.281524…`, which rounds to `45.2815`. The `0.0002pp` difference
    is inside the 0.05 tolerance, but the ground truth should use the exact rounded value.
12. **README counts / dataset defaults:** 7 cases vs 5, 3 controllers vs 4, and
    `dataset.toml:12` judge timeout 30 vs task 180. Stale but low impact.
13. **`design:310` "all checks carry submission_paths":** only the two LLM checks do; command
    checks receive `/submission` and read it directly. Documentation nit.
14. **`design:320` invalid-submission penalty:** says ">3 次错误提交扣 5"; implementation
    deducts `0.05` per rejected submission, capped at `0.2`. Documentation/implementation
    mismatch.
15. **`design:318` segment tolerance:** says `±0.1pp`; implementation uses `0.05`. This is
    mostly harmless (tighter), but the docs should match.
16. **`judge/README.md` / `judge/rubric.json`:** referenced by the design (`:325`) but absent.

---

## 4. Check results

### 4.1 Timeline and anchors — **PASS**

The fixture mapping is exact and consistent across the scenario, DB, ground truth and design.

| Anchor | Real/UTC | Business seconds | Evidence |
|---|---|---|---|
| Shift start 15:00 ET | 2026-04-29T19:00:00Z | 0 | `scenario.json:5`; `ground_truth.json:6`; `build_equity_event_db.py` EPOCH |
| 4/29 close 16:00 ET | 2026-04-29T20:00:00Z | 3,600 | `scenario.json:10-11`; DB `prices` 4/29 `available_at_s=3600` |
| 8-K accepted 16:01:35 ET | 2026-04-29T20:01:35Z | **3,695** | `data/filings.csv:5`; `scenario.json:12-14`; `ground_truth.json:39`; `design:73` |
| Forecast deadline 15:55 | — | 3,300 | `scenario.json:8`; `manual.md:26`; `design:314` |
| Reconciliation 16:20 | — | 4,800 | `scenario.json:8`; `manual.md:27`; `design:317` |
| 10-Q accepted 21:02:11 ET | 2026-04-30T01:02:11Z | **21,731** | `data/filings.csv:6`; `scenario.json:15-17`; `ground_truth.json:41`; `design:74` |
| Verification 21:20 | — | 22,800 | `scenario.json:8`; `manual.md:28`; `design:318` |
| Shift end 21:30 | — | 23,400 | `scenario.json:6`; `ground_truth.json:6` |

`python3` DB checks confirmed the GOOGL filings are `0, 0, 0, 3695, 21731` and the docs
`0, 0, 0, 3695, 3695, 21731`; 4/29 close is `3600`; 4/30 close is `90000`.

**Conclusion:** no timeline blocker. The only date-label nit is the design's 3/24 consensus
snapshot vs the 3/17 `as_of` timestamp (Minor 2).

### 4.2 Numeric consistency — **PASS** (one 0.0002pp precision nit)

Recomputed from `data/docs/000043_ex99_1.txt` and `data/docs/000048_primary.txt`:

| Metric | Recomputed | `judge/ground_truth.json` | Source lines |
|---|---:|---:|---|
| Total revenue | 109,896 | 109,896.0 | PR `:26,52`; 10-Q `:197,294`; GT `:9` |
| TAC | 15,228 | 15,228.0 | PR `:53`; 10-Q `:354`; GT `:10` |
| Net revenue | 109,896 − 15,228 = **94,668** | 94,668.0 | PR does not print net; 10-Q does not print net; GT `:11` |
| Diluted EPS | 5.11 | 5.11 | PR `:37`; 10-Q `:212`; GT `:12` |
| Operating income | 39,696 | 39,696.0 | PR `:30,65`; 10-Q `:204`; GT `:14` |
| Net income | 62,578 | 62,578.0 | PR `:35`; 10-Q `:208`; GT `:13` |
| Operating margin | 39,696 / 109,896 = **36.121424%** | 36.1214 | GT `:15` |
| Google Services revenue | 89,637 | 89,637.0 | PR `:48`; 10-Q `:290`; GT `:16` |
| Google Services op income | 40,589 | 40,589.0 | PR `:60`; GT `:17` |
| Google Services margin | 40,589 / 89,637 = **45.281524%** | 45.2817 | GT `:20`; **nit: should be 45.2815** |
| Google Cloud revenue | 20,028 | 20,028.0 | PR `:49`; 10-Q `:291`; GT `:18` |
| Google Cloud op income | 6,598 | 6,598.0 | PR `:61`; GT `:19` |
| Google Cloud margin | 6,598 / 20,028 = **32.943879%** | 32.9439 | GT `:21` |
| Consensus net revenue | 91.69 USD bn = 91,690 USD m | 91,690.0 | `consensus.csv:2`; GT `:23` |
| Consensus EPS | 2.76 | 2.76 | `consensus.csv:3`; GT `:23` |
| Net surprise | 94,668 / 91,690 − 1 = **3.247901%** | 3.2479 | GT `:24` |
| EPS surprise | 5.11 / 2.76 − 1 = **85.144928%** | 85.1449 | GT `:24` |
| Beat/miss | both beat (thresholds +0.5%) | beat/beat | `manual.md:44-46`; GT `:25` |

Cross-checks:

- Q1 2025 net revenue `90,234 − 13,748 = 76,486`; `91,690 / 76,486 − 1 = 19.878%`, matching
  the consensus note's "20% year-over-year growth" (`consensus.csv:2`).
- Q1 2025 EPS `2.81`; `2.76 / 2.81 − 1 = −1.779%`, matching the "1.8% decline" note
  (`consensus.csv:3`).
- 4/30 close `384.80 / 349.94 − 1 = 9.9617%`, matching the design's `+9.96%`.

The XBRL Q1 2026 facts agree: `Revenues 109,896,000,000`, `OperatingIncomeLoss 39,696,000,000`,
`NetIncomeLoss 62,578,000,000`, `EarningsPerShareDiluted 5.11`, all at
`available_at_s=21731` (DB query; 10-Q filed `2026-04-30T01:02:11Z`).

**Conclusion:** the displayed numbers are not fabricated and are mutually consistent. The
only precision issue is the Services margin `45.2817` vs exact `45.2815`, well inside the
0.05 tolerance. The 10-Q does **not** print net revenue; that is correctly documented as a
derived figure in `EXTRACTION_REPORT.md:1.1` and `judge/ground_truth.json:55-60`.

### 4.3 Agent-facing manual and prompt — **FAIL**

**What is good**

- `prompt.md:1-10` contains no pre-computed answer table, no step-by-step hint, and correctly
  points to `desk/manual.md`.
- Core schema fields in `manual.md:52-78` match what `engine.py:198-262` validates:
  forecast four numbers + two probabilities + optional basis; reconciliation four actuals +
  consensus net/EPS + two surprises + beat/miss + source_doc_ids; verification seven GAAP +
  consistency bool + two segment margins + source_doc_ids.
- Definitions (`manual.md:39-46`) match the judge's formulas: net = total − TAC; operating
  margin = op income/total; segment margin = segment op income/segment revenue; surprise
  formulas; beat/miss threshold.
- Reporting units and precision are stated (`manual.md:33-36`), apart from the leak examples.

**What fails**

- **Leak:** the examples are exact actuals (`manual.md:33-34`; B2).
- **10-Q verification gap:** segment margins are not in the 10-Q (`manual.md:28`,
  `manual.md:71-78`; B3).
- **Rubric fields missing:** no locator, memo, exceptions, notes, or method in the documented
  schema, while the LLM rubrics require them (`rubric_evidence.json:11,15`;
  `rubric_logic.json:15`; M1).
- **Unit trap:** consensus is USD billions (`consensus.csv:2`) while company figures are USD
  millions (`manual.md:33`); the manual does not explicitly say to multiply by 1,000.
- **Evidence audit gap:** forecast has no `source_doc_ids`; `basis` is free text; the audit
  only checks `source_doc_ids` (`verify_ingest.py:173-207`; M9).

**Conclusion:** a careful analyst can act on the reconciliation and most of the verification,
but the pre-release forecast is compromised by the leak and the score design, and the
verification request is not fully supported by the named filing.

### 4.4 Design claims vs implementation — **FAIL**

Material gaps, in addition to B1/B3:

| Design claim | Implementation | Evidence |
|---|---|---|
| Consensus is total revenue 91.69B (`:69`) | Data/GT/manual use net revenue 91.69B | `consensus.csv:2`; `ground_truth.json:23`; `manual.md:69` |
| Reference net = 91,690 − TAC ≈ 82.5–83k (`:300`) | Arithmetic inconsistent; actual 94,668 | B1; `design:300` |
| Reconciliation 5 pts/actual, sum 30 (`:317`) | 3 pts/actual, max 20 | `verify_ingest.py:91-119` |
| Segment margin tolerance 0.1pp (`:318`) | 0.05pp for all | `verify_ingest.py:150-155` |
| `judge/rubric.json` + `judge/README.md` (`:325`) | `rubric_evidence.json` + `rubric_logic.json`; no README | package listing |
| E1–E4 weight 2 (`:336-347`) | 4 criteria weight 1 | rubric files |
| Budget 160 (`:203`) | 120 | `scenario.json:7`; `manual.md:9`; `prompt.md:8` |
| All peer data at 0 (`:160`) | Peer 8-Ks at 3811/3941/4735; close 3600 | DB `issuer_events`/`prices` |
| Hidden `_hidden_*` tables (`:151`) | No hidden tables | DB schema |
| Anti-leak/calibration tests recorded (`:362-381`) | `docs/calibration/` has only source-treasury | `find` output |
| 295 assertions, all deterministic 1.0 (`:419,429`) | No validator; consensus forecast 0.0 | B1; no file |
| Consumed by 9 issuers/200+ peer events (`:182-186`) | 9 issuers but 12 events, 0 peer docs, 0 peer prices | DB counts |

**Conclusion:** the design document describes a richer, differently scored case than the one
shipped. The timeline/DB mapping is the strongest implemented part.

### 4.5 Provenance and spot checks — **PARTIAL / FAIL**

**Supported**

- `build_provenance.json` hashes match all 10 data files and `market.db`; DB is 3,616,768
  bytes, SHA-256 `4ae6eb90…`.
- The 14 present data files match their manifest sha256/bytes.
- `data/docs/000043_ex99_1.txt` headers contain the SEC accession and source URL; 10-Q and
  10-K headers similarly.
- 10+ numbers spot-checked against the press release/10-Q (table in 4.2); no fabricated
  "real" number was found. `94,668` appears only inside `194,668` in the release and is
  correctly labeled a derived figure in `EXTRACTION_REPORT.md:1.1` and
  `ground_truth.json:55-60`.
- 4/29 close, 4/28 close, 4/30 close and 5/1 close map to the DB `available_at_s` values
  (`3600`, `0`, `90000`, `176400`).

**Not supported / gaps**

- 33 of 47 manifest entries are absent: 28 `raw/` files and 5 scripts/internal files.
  `total_bytes` (`14,357,415`) includes them; present data is `4,325,168`.
- All 14 `data/` entries lack `source_url`; only sha256/bytes are present.
- `EXTRACTION_REPORT.md:149` cites `scripts/dl.py`; no `scripts/` directory exists.
- `data/o19_ground_truth.json` is a post-event judge-side file (`public_available_at
  2026-06-19T13:00:05Z`) sitting under `data/`, not `judge/` (M8).
- `build_equity_event_db.py:158` and `EXTRACTION_REPORT.md:73` say "no post-event facts", but
  the DB contains 542 rows filed after the event (269 at 2026-07-23, 273 at 2026-10-29). They
  are correctly hidden by `available_at_s`, so this is a misleading provenance statement, not
  an observed live leak.

**Anti-leak runtime check (positive)**

Using the real `DataService` at selected clock values:

| Clock | issuers | filings | documents | xbrl | consensus | prices | events |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 9 | 17 | 3 | 19,829 | 4 | 582 | 6 |
| 3,695 | 9 | 18 | 5 | 19,829 | 4 | 583 | 7 |
| 21,731 | 9 | 25 | 6 | 20,235 | 4 | 583 | 11 |

At t=0, `read("googl-8k-20260429-ex991")` and `read("googl-10q-20260331")` are rejected;
the Q1 2026 XBRL query returns 0 rows. At t=3695 the EX-99.1 read succeeds (23,561 chars),
but the 10-Q is still rejected. At t=21731 the 10-Q read succeeds (22,857 chars) and the
XBRL `Revenues` query returns `109,896,000,000`. The tool-layer gating works; the problem is
the manual leak, not the DB.

---

## 5. Commands used

All commands were read-only; the only repo write is this report. Temporary judge inputs were
created under `<workdir>/equity-verify`, outside the repository.

```bash
# Repo/task inspection
git -C <repo> status --short
find tasks -maxdepth 2 -name task.toml | sort
find workflows -maxdepth 2 -name harness.toml | sort
find docs/calibration -maxdepth 1 -type f | sort

# Line-number evidence
nl -ba tasks/equity-event-001/environment/initial_workspace/desk/manual.md | sed -n '22,80p'
nl -ba tasks/equity-event-001/workflow-fixtures/scenario.json
nl -ba tasks/equity-event-001/judge/ground_truth.json | sed -n '5,40p'
nl -ba tasks/equity-event-001/task.toml | sed -n '1,121p'
nl -ba docs/design/equity-event-stream-case-design.md | sed -n '63,75p;180,186p;295,326p;354,370p;415,437p'

# DB counts and availability
python3 - <<'PY'
import sqlite3
c = sqlite3.connect('tasks/equity-event-001/environment/initial_workspace/market.db')
# table counts, GOOGL filing availability, docs, prices, issuer_events, xbrl
PY

# DataService time-gating probe (real controller service)
python3 - <<'PY'
import sys
sys.path.insert(0, 'workflows/equity-event-stream')
from data_service import DataService
# instantiate at now=0, 3695, 21731; catalog/query/read
PY

# Judge reproduction
mkdir -p <workdir>/equity-verify
python3 - <<'PY'
# build evidence/equity_event.json with consensus forecast 91,690/2.76
# and perfect reconciliation/verification
PY
for check in forecast_revenue forecast_eps probabilities reconciliation_actuals \
             tenq_verification timeliness audit_integrity; do
  python3 tasks/equity-event-001/judge/verify_ingest.py \
    --scenario tasks/equity-event-001/judge/ground_truth.json \
    --submission <workdir>/equity-verify \
    --result <workdir>/equity-verify/$check.json \
    --check $check
done

# Numeric checks
python3 - <<'PY'
print(109896 - 15228)
print(39696 / 109896 * 100)
print(40589 / 89637 * 100)
print(6598 / 20028 * 100)
print((94668 / 91690 - 1) * 100)
print((5.11 / 2.76 - 1) * 100)
PY

# 10-Q segment gap
grep -n '40,589\|6,598' tasks/equity-event-001/data/docs/000048_primary.txt
grep -n '40,589\|6,598' tasks/equity-event-001/data/docs/000043_ex99_1.txt
grep -n 'Google Services\|Google Cloud' tasks/equity-event-001/data/docs/000048_primary.txt

# Manifest/hash checks
python3 - <<'PY'
import json, hashlib, pathlib
m = json.load(open('tasks/equity-event-001/data/EXTRACTION_MANIFEST.json'))
# count source_url presence, verify 14 data files, 28 raw absent, 5 scripts absent
PY
python3 - <<'PY'
import json, hashlib, pathlib
p = json.load(open('tasks/equity-event-001/build_provenance.json'))
# verify db_sha256/db_bytes and 10 data_files hashes
PY
```

Key judge output from the reproduction:

```text
forecast_revenue       0.0   fail   expected_net_revenue 94668.0
forecast_eps           0.0   fail   forecast_eps 2.76
probabilities          1.0   pass   brier 0.0
reconciliation_actuals 1.0   pass   (4×3 + 2×2 + 2×2) / 20
tenq_verification      1.0   pass
timeliness             1.0   pass
audit_integrity        1.0   pass
weighted mean          0.80  < 0.95
```

---

## 6. Recommended fixes, in priority order

1. **Fix forecast scoring (B1).** Either score the forecast against a realistic pre-release
   band/method (e.g. consensus net ± a documented TAC sensitivity) rather than the post-release
   actual, or make the forecast checks non-blocking for the pass threshold and let the
   reconciliation/verification carry the case. If the point checks stay, do not claim the
   design reference path is realistic.
2. **Remove leaked actuals from the manual (B2).** Replace `109896.0` and `36.12` with
   placeholders or pre-shift values; add a test that scans manual/prompt for every actual in
   `ground_truth.json`.
3. **Fix the verification task (B3).** Either add segment operating income to the 10-Q text
   (if it can be sourced) or change the manual/design to say segment margins are verified from
   EX-99.1, with the 10-Q used only for GAAP totals. Do not call it "10-Q verification of
   segment margins" if the 10-Q has no segment operating income.
4. **Unify the schema (M1).** Choose either the design schema (`basis` objects with
   `source_doc_id`/`locator`, `method`, `notes`, `memo`, `exceptions`, `as_of`) or the manual
   schema, and update `engine.py`, `manual.md`, the design and both rubrics together. Add a
   documented place for the rubric's locators/memo.
5. **Fix the design's consensus math (M4).** Decide whether 91.69B is total or net. If net,
   remove the TAC subtraction at `design:300`; if total, use a consistent net figure and
   recompute the reference. Make `:69`, `:300`, `:431`, `consensus.csv`, and `ground_truth`
   use the same label.
6. **Reconcile design and judge details (M5).** Correct the reconciliation point allocation,
   segment tolerance, rubric filenames, and §12.1 weights. Either ship `judge/rubric.json` and
   `judge/README.md` or remove the references.
7. **Fix provenance (M3).** Add `source_url` to every data entry, include the raw files and
   `scripts/` (or remove the claims), make `total_bytes` reflect present files, and correct
   `EXTRACTION_REPORT.md:7,124,149`. Fix the "no post-event facts" wording at
   `build_equity_event_db.py:158` and `EXTRACTION_REPORT.md:73`.
8. **Meet or restate scale targets (M2).** Add peer documents, peer prices, and the intended
   peer-event volume, or lower the design's §5.5 targets to what is actually shipped.
9. **Update README/dataset (M6).** Remove "no LLM Judge", update the case/workflow counts and
   description, and reconcile the judge timeout defaults.
10. **Record anti-leak/calibration evidence (M7).** Add the §13 test results and the §14
    calibration file, or delete the claims. Fix the unsupported "295 assertions"/"all 1.0"
    statements.
11. **Move judge-side post-event truth under `judge/` or explicitly label `data/` as
    judge-only (M8).** Do not mix post-event truth with the build fixtures.
12. **Fix the Services margin (minor 11).** Use `45.2815` (exact rounding) in
    `judge/ground_truth.json:20`, or document the source of the `45.2817` value.

---

## 7. Bottom line

- **Timeline/anchors:** PASS — scenario, DB, ground truth and design agree on `3695` and
  `21731`, and the 4/29 close at `3600`.
- **Numeric consistency:** PASS — all displayed actuals/consensus/surprises reconcile; one
  `0.0002pp` Services margin precision nit; net revenue is correctly derived, not printed.
- **Manual/prompt:** FAIL — exact actuals leaked, 10-Q segment-margin verification impossible,
  rubric fields undocumented.
- **Design vs implementation:** FAIL — consensus basis, reference forecast, reconciliation
  points, segment tolerance, rubric files, scale targets, and calibration/validation claims
  do not match.
- **Provenance:** PARTIAL/FAIL — data hashes and DB hash are good; 33/47 manifest entries are
  absent and the 14 data entries have no source URLs.
- **Overall verdict: FAIL.** The case is not ready for use as a realistic, internally
  consistent benchmark until B1–B3 and the major documentation/provenance gaps are fixed.
