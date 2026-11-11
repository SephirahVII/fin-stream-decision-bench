# Solvability Review — `equity-event-001`

**Case:** `tasks/equity-event-001` (Alphabet Q1 2026 earnings night)
**Review type:** independent reference solution + deterministic judge + rubric/derivability audit
**Date:** 2026-11-11
**Reference harness:** `<workdir>/refsol/run_reference.py`
**Evidence:** `<workdir>/refsol/evidence.json`
**Verdict:** **SOLVABLE WITH FIXES** — mechanically sound and fully derivable for reconciliation/verification, but **not passable at the 0.95 threshold as configured** for a good-faith solver. The blocker is `forecast_eps`: the scored target 5.11 contains a $2.35 one-time equity-securities gain that is not observable before the 8-K. A defensible EPS forecast scores 0; the maximum defensible full-case score is ~91.99/100, and the independent reference scores 85.02/100 (with rubrics assumed full).

---

## 1. Summary

| Question | Answer |
|---|---|
| Can a reference solution be built using only `Desk` / `DataService`? | Yes. `<workdir>/refsol/run_reference.py` imports `Desk` from `workflows/equity-event-stream/engine.py`, uses the task DB and fixture, and drives a valid 16-action sequence. |
| Are reconciliation and verification derivable at the right times? | Yes. The 8-K EX-99.1 is available at t=3695; the 10-Q at t=21731. Every scored reconciliation and verification field is printed in those documents. |
| Is the forecast derivable before t=3300? | **Partly.** Revenue/TAC/net revenue are estimable from t=0 data; the actual +3.25% revenue beat is at the edge of a defensible range (0.445 score for a 20.5%-growth model, 0.907 for a 21.5% bull case). The GAAP EPS target 5.11 is **not** estimable: consensus is 2.76 and the $2.35 one-time gain is only in the post-release 8-K. |
| Does the reference earn all deterministic checks? | Reconciliation 20/20, timeliness 10/10, audit 10/10; verification 0.9996/1.0 (Google Services margin ground-truth typo); forecast revenue 0.4449/1.0; forecast EPS 0/1.0; probabilities 0.96875/1.0. Deterministic weighted sum **70.0203 / 85 (82.38%)**; full case with rubrics full **85.0203 / 100**. |
| Does the case pass its own 0.95 threshold? | **No** for the reference and no for any defensible forecast. Only an oracle/lucky EPS guess (>= ~4.923) plus near-perfect everything else passes. |
| Is timing feasible? | Yes, comfortably. 16 actions, submissions at t=105 / 3,715 / 21,761; all deadlines met with >1,000 s slack; budget 120. |
| Is the manual/schema/judge internally consistent? | Mostly, but there are material inconsistencies: the design doc treats 91,690 as *total* revenue and recommends an 82,500–83,000 net-revenue forecast, contradicting the manual/ground truth (91,690 is net of TAC); the rubric narrative field `summary` is undocumented; the Google Services margin ground truth is slightly wrong; design weights/tolerances/budget differ from the judge. |

**Bottom line:** the evidence-chain mechanics are solvable and the reconciliation/verification half is strong; the forecast-EPS calibration makes the case a lottery at the 0.95 threshold. Fix the EPS basis (score core EPS, or explicitly handle one-time gains), document the narrative field, and correct the design/ground-truth inconsistencies; then the case is genuinely solvable.

---

## 2. Reference solution

### 2.1 Harness

- DB: `tasks/equity-event-001/environment/initial_workspace/market.db`
- Fixture: `tasks/equity-event-001/workflow-fixtures/scenario.json` (loaded by the harness as `TASK / 'workflow-fixtures' / 'scenario.json'`)
- Manual: passed to `Desk(..., public_files={'desk/manual.md': <manual text>})`
- The script imports `Desk` directly and calls `desk.act({...})`; it does not use the controller's LLM loop.
- No task/workflow/judge file was modified. The only repo write is this report.

### 2.2 Action sequence (16 actions)

| # | Action | at_s | Cost | Deadline | Slack |
|---:|---|---:|---:|---:|---:|
| 1 | `read(path="desk/manual.md")` | 10 | 10 | 3300 | 3290 |
| 2 | `query` consensus_estimates (est-01/est-02) | 25 | 15 | 3300 | 3275 |
| 3 | `query` XBRL Revenues 2024–2025 | 40 | 15 | 3300 | 3260 |
| 4 | `query` XBRL CostOfRevenue 2024–2025 | 55 | 15 | 3300 | 3245 |
| 5 | `query` XBRL equity-securities gains (FY2025, Q1 2025) | 70 | 15 | 3300 | 3230 |
| 6 | `read("googl-10k-20251231")` | 80 | 10 | 3300 | 3220 |
| 7 | `query` prices (GOOGL, latest visible) | 95 | 15 | 3300 | 3205 |
| 8 | `submit("forecast", ...)` | **105** | 10 | 3300 | 3195 |
| 9 | `wait()` → 3600 market update | 3600 | 0 | — | — |
| 10 | `wait()` → 3695 8-K release | 3695 | 0 | — | — |
| 11 | `read("googl-8k-20260429-ex991")` | 3705 | 10 | 4800 | 1095 |
| 12 | `submit("reconciliation", ...)` | **3715** | 10 | 4800 | 1085 |
| 13 | `wait()` → 21731 10-Q release | 21731 | 0 | — | — |
| 14 | `read("googl-10q-20260331")` | 21741 | 10 | 22800 | 1059 |
| 15 | `read("googl-8k-20260429-ex991")` (compare) | 21751 | 10 | 22800 | 1049 |
| 16 | `submit("verification", ...)` | **21761** | 10 | 22800 | 1039 |

`actions_used=16`, `business_time_s=21761`, shift end 23400; 104 actions of the 120 budget unused.

### 2.3 Forecast (pre-release only)

All inputs below are visible at t=0 or before t=105. The reference deliberately does **not** use the actual Q1 2026 print.

| Input | Value (USD m) | Source / derivation |
|---|---:|---|
| Consensus net revenue | 91,690 | `consensus_estimates` est-01, available t=0; note says "net of TAC", +20% YoY |
| Consensus GAAP diluted EPS | 2.76 | `consensus_estimates` est-02, available t=0 |
| Q1 2025 revenue | 90,234 | XBRL `RevenueFromContractWithCustomerExcludingAssessedTax` from 2025-04-25 10-Q, available t=0 |
| Q2/Q3/Q4 2025 revenue | 96,428 / 102,346 / 113,828 | XBRL `Revenues`, available t=0; Q4 = FY2025 402,836 − Q1−Q3 |
| Q1 2025 cost of revenues | 36,361 | XBRL `CostOfRevenue`, available t=0 |
| FY2025 cost of revenues | 162,535 | XBRL `CostOfRevenue`, available t=0 |
| FY2025 TAC | 59,926 | 10-K text `TAC $ 54,900 $ 59,926` |
| FY2025 Google advertising | 294,691 | 10-K text |
| Q1 2025 TAC estimate | 13,406 | 59,926 × 36,361 / 162,535 |
| Q1 2025 net revenue estimate | 76,828 | 90,234 − 13,406 |
| Revenue growth trend | 12.0% → 13.8% → 15.9% → 18.0% | YoY quarterly; OLS next-quarter 20.0% |
| FY2025 equity-securities gain | 24.08 B | XBRL `EquitySecuritiesFvNiGainLoss`, available t=0 |
| Q1 2025 equity-securities gain | 9.96 B | XBRL `DebtAndEquitySecuritiesGainLoss`, available t=0 |
| 2026-04-28 close | 349.78 | `prices`, available t=0 (the 4/29 close is at t=3600, after the forecast deadline) |

**Model and submission:**

| Field | Reference value | Derivation |
|---|---:|---|
| `total_revenue_usd_m` | 108,731.97 | Q1 2025 90,234 × 1.205 (trend 20.0% + 0.5pp AI/Cloud lift) |
| `tac_usd_m` | 14,852.218 | Google advertising 74,261.1 × 20.0% TAC rate |
| `net_revenue_usd_m` | 93,879.752 | 108,731.97 − 14,852.218 |
| `diluted_eps_usd` | 3.25 | consensus 2.76 + ~1.4% buyback to 2.80 core + ~0.45 normal equity gain |
| `probabilities.net_revenue_beat` | 0.75 | model net +2.4% vs consensus; subjective |
| `probabilities.eps_beat` | 0.75 | model EPS +17.8% vs consensus; subjective |

The basis text cites the frozen consensus, visible XBRL history, the 10-K TAC/advertising structure, the equity-gain history, and the 4/28 close. It does not contain the actual 5.11, 109,896, 94,668, 36.9B or 2.35 figures.

### 2.4 Reconciliation (after t=3695)

| Field | Value |
|---|---:|
| `actuals.total_revenue_usd_m` | 109,896 |
| `actuals.tac_usd_m` | 15,228 |
| `actuals.net_revenue_usd_m` | 94,668 = 109,896 − 15,228 |
| `actuals.diluted_eps_usd` | 5.11 |
| `consensus.net_revenue_usd_m` | 91,690 |
| `consensus.diluted_eps_usd` | 2.76 |
| `surprise.net_revenue_pct_vs_consensus` | 3.2479 = (94,668 / 91,690 − 1) × 100 |
| `surprise.eps_pct_vs_consensus` | 85.1449 = (5.11 / 2.76 − 1) × 100 |
| `beat_miss.net_revenue` | `beat` (+3.2479 > +0.5) |
| `beat_miss.eps` | `beat` (+85.1449 > +0.5) |
| `source_doc_ids` | `["googl-8k-20260429-ex991"]` |

All values are printed in the EX-99.1; net revenue itself is not printed and is derived. `reconciliation_actuals` scored **20/20**.

### 2.5 Verification (after t=21731)

| Field | Value | Source |
|---|---:|---|
| `gaap.total_revenue_usd_m` | 109,896 | 10-Q income statement; matches EX-99.1 |
| `gaap.tac_usd_m` | 15,228 | 10-Q MD&A cost of revenues; matches EX-99.1 |
| `gaap.net_revenue_usd_m` | 94,668 | 109,896 − 15,228 |
| `gaap.operating_income_usd_m` | 39,696 | 10-Q income statement; matches EX-99.1 |
| `gaap.operating_margin_pct` | 36.1214 | 39,696 / 109,896 × 100 |
| `gaap.net_income_usd_m` | 62,578 | 10-Q income statement; matches EX-99.1 |
| `gaap.diluted_eps_usd` | 5.11 | 10-Q income statement; matches EX-99.1 |
| `consistency.press_release_matches_10q` | `true` | Revenues, operating income, diluted EPS all match |
| `segment_margins_pct.google_services` | 45.2815 | 40,589 / 89,637 × 100 (EX-99.1 segment table) |
| `segment_margins_pct.google_cloud` | 32.9439 | 6,598 / 20,028 × 100 (EX-99.1 segment table) |
| `source_doc_ids` | `["googl-8k-20260429-ex991", "googl-10q-20260331"]` | both published by t=21731 |

The 10-Q extract has no segment operating income table; segment margins are only in the release segment table. The summary explicitly notes this, which also serves as the L4 case-specific cross-check.

### 2.6 Evidence and judge run

`Desk.export()` was written to `<workdir>/refsol/evidence.json`; the submission directory is `<workdir>/refsol/submission/evidence/equity_event.json`. The judge was run for all seven deterministic check ids with the case's exact command. Results are in `<workdir>/refsol/result_<check>.json`.

---

## 3. Deterministic judge results

| Check | Weight | Score | Contribution | Judge outcome | Notes |
|---|---:|---:|---:|---|---|
| `forecast_revenue` | 12 | 0.444904 | 5.3388 | fail | 93,879.752 vs 94,668; error 788.248 vs tolerance 1,420.02 |
| `forecast_eps` | 8 | 0.000000 | 0.0000 | fail | 3.25 vs 5.11; error 1.86 > 0.30 tolerance |
| `probabilities` | 10 | 0.968750 | 9.6875 | fail (score < 1) | Brier 0.0625; 0.75/0.75 vs both true |
| `reconciliation_actuals` | 20 | 1.000000 | 20.0000 | pass | 4×3 actuals + 2×2 surprises + 2×2 calls |
| `tenq_verification` | 15 | 0.999600 | 14.9940 | fail (score < 1) | 9/10 items at 1.0; GS margin item 0.996 |
| `timeliness` | 10 | 1.000000 | 10.0000 | pass | 105/3,715/21,761 all ≤ deadlines |
| `audit_integrity` | 10 | 1.000000 | 10.0000 | pass | no unknown/early docs; no failed reads/submits |
| **Deterministic total** | **85** | **0.823769** | **70.0203** | **fail at 0.95** | deterministic mean 0.8238 |
| Rubric checks (not executed) | 15 | 1.0 assumed | 15.0000 | — | E1–E4/L1–L4 statically assessed |
| **Full case** | **100** | **0.850203** | **85.0203** | **fail at 0.95** | with all rubrics full |

The per-check `outcome` is the judge's strict `score >= 0.999999` flag; the aggregate uses the `score`, not the flag. `probabilities` and `tenq_verification` are "fail" only because they are just under 1.0. The full-case 85.02 assumes all four evidence and four logic rubric criteria are awarded; the deterministic-only result is 82.38%.

**Why `tenq` is 0.9996:** the ground truth says Google Services margin 45.2817, but the exact ratio is 40,589 / 89,637 × 100 = **45.281524**, which rounds to 45.2815. The 0.05pp tolerance gives the item 0.996, so `tenq` = 0.9996 and can never reach the judge's 0.999999 pass flag even with perfect data. This costs 0.006/100 in the aggregate; it is a ground-truth typo, not a solver error.

---

## 4. Achievability envelope

The forecast checks are point-prediction checks; the other five deterministic checks are fully earnable. The table shows what different pre-release strategies score (all with the same perfect reconciliation/verification/timeliness/audit and full rubrics).

| Strategy | Forecast net revenue | Forecast EPS | Probabilities | Deterministic /85 | Full case /100 | Pass 0.95? |
|---|---:|---:|---:|---:|---:|---|
| Bare consensus | 91,690 | 2.76 | 0.50/0.50 | 63.744 | 78.744 | no |
| Reference base (20.5% growth) | 93,879.8 | 3.25 | 0.75/0.75 | 70.020 | 85.020 | no |
| Bull (21.5% growth) | ~94,536 | 3.60 | 0.80/0.80 | 75.679 | 90.679 | no |
| Max defensible (actual revenue, EPS 3.60) | 94,668 | 3.60 | 1.00/1.00 | 76.994 | **91.994** | no |
| Near-oracle (actual revenue, EPS 4.95) | 94,668 | 4.95 | 0.99/0.99 | 80.727 | 95.727 | yes, but EPS not defensible |
| Oracle | 94,668 | 5.11 | 0.99/0.99 | 84.993 | 99.993 | yes |

The "max defensible" row is derived analytically; the others were run through the judge. The **EPS cliff**:

- With every other check perfect and all rubrics full, the non-EPS contribution is 91.994.
- To reach 95.000, `forecast_eps` must contribute ≥ 3.006/8 → score ≥ 0.37575 → `|EPS − 5.11| ≤ 0.187275` → **EPS ≥ 4.9227** (or ≤ 5.297).
- A defensible pre-release EPS is 2.7–3.6 (consensus 2.76; base 3.25; bull 3.60). It scores **0**; there is no partial credit below 4.81.
- The actual 5.11 is 5.11 − 2.35 = 2.76 **core** EPS plus a $36.9B pre-tax unrealized equity-securities gain. The 2.35 contribution is only disclosed in the 8-K EX-99.1 footnote (t=3695) and the 10-Q note (t=21731); it is not in any pre-3300 document or XBRL fact.

The **revenue cliff** is less severe but still narrow:

- Any points require 93,247.98 < net revenue < 96,088.02 (tolerance 1,420.02 around 94,668).
- Consensus 91,690 scores 0. The base 93,879.8 scores 0.4449; a 21.5% bull ~94,536 scores 0.9071; a 22.0% model is needed for 1.0. The actual +3.25% beat is at the top of the plausible pre-release range; the design's "generous ±1.5%" claim is not generous relative to that beat.

The **probability check** is easy: 0.75/0.75 scores 0.96875; 0.80/0.80 scores 0.98; 0.99/0.99 scores 0.9999. It does not compensate for the EPS loss.

---

## 5. Field derivability

Legend: **Exact** = printed in a document visible at the stated time; **Estimate** = derivable as a forecast, not exact; **No** = not derivable from visible data at the required time.

| Scored field | Source (table/doc) | Visible at t | Derivation | Status |
|---|---|---:|---|---|
| `forecast.total_revenue_usd_m` | consensus est-01 (91,690 net) + 10-K TAC/advertising + XBRL revenue/cost | 0 | net + TAC model; or Q1 2025 × growth | Estimate |
| `forecast.tac_usd_m` | 10-K TAC 59,926; advertising 294,691; XBRL Q1 2025 cost 36,361 / FY 162,535 | 0 | Q1 2025 TAC = 59,926 × 36,361/162,535; Q1 2026 TAC = rate × advertising | Estimate |
| `forecast.net_revenue_usd_m` | same | 0 | total − TAC; consensus anchor 91,690 | Estimate (tol 1,420.02) |
| `forecast.diluted_eps_usd` | consensus 2.76; XBRL FY2025 gain 24.08B, Q1 2025 9.96B | 0 | core + normal equity gain → 3.25; actual 5.11 includes 2.35 one-time gain | **No** (blocker) |
| `probabilities.*` | model | 0 | judgment | Estimate |
| `reconciliation.actuals.total_revenue_usd_m` | EX-99.1 income statement | 3695 | direct | Exact |
| `reconciliation.actuals.tac_usd_m` | EX-99.1 cost-of-revenues table | 3695 | direct | Exact |
| `reconciliation.actuals.net_revenue_usd_m` | EX-99.1 | 3695 | 109,896 − 15,228 | Exact |
| `reconciliation.actuals.diluted_eps_usd` | EX-99.1 income statement | 3695 | direct | Exact |
| `reconciliation.consensus.*` | consensus_estimates | 0 | 91,690 / 2.76 | Exact |
| `reconciliation.surprise.*` | arithmetic | 3695 | (actual/consensus − 1) × 100 | Exact |
| `reconciliation.beat_miss.*` | manual thresholds | 3695 | > +0.5 / < −0.5 | Exact |
| `verification.gaap.total_revenue_usd_m` | 10-Q income statement; EX-99.1 | 21731 | direct; matches | Exact |
| `verification.gaap.tac_usd_m` | 10-Q MD&A cost of revenues; EX-99.1 | 21731 | direct; matches | Exact |
| `verification.gaap.net_revenue_usd_m` | 10-Q / EX-99.1 | 21731 | 109,896 − 15,228 | Exact |
| `verification.gaap.operating_income_usd_m` | 10-Q income statement; EX-99.1 | 21731 | direct; matches | Exact |
| `verification.gaap.operating_margin_pct` | arithmetic | 21731 | 39,696/109,896 × 100 | Exact |
| `verification.gaap.net_income_usd_m` | 10-Q income statement; EX-99.1 | 21731 | direct; matches | Exact |
| `verification.gaap.diluted_eps_usd` | 10-Q income statement; EX-99.1 | 21731 | direct; matches | Exact |
| `verification.segment_margins_pct.google_services` | EX-99.1 segment table | 3695 | 40,589/89,637 × 100 | Exact |
| `verification.segment_margins_pct.google_cloud` | EX-99.1 segment table | 3695 | 6,598/20,028 × 100 | Exact |
| `verification.consistency.press_release_matches_10q` | comparison | 21731 | revenue/op income/EPS match | Exact |
| `source_doc_ids` | documents table | 3695/21731 | exact DB doc ids | Exact |
| `timeliness` | submission timestamps | 105/3715/21761 | all ≤ deadlines | Exact |
| `audit_integrity` | journal + doc metadata | submission times | valid/published citations; no failed reads | Exact |

**Blocker:** `forecast.diluted_eps_usd`. The only pre-release EPS path is consensus 2.76 plus a normal equity-securities gain; that lands at 3.25, 1.86 below the target 5.11 (tolerance 0.30). The actual one-time gain is not derivable before the 8-K. No amount of pre-release modeling closes this gap.

**Not a blocker but tight:** `forecast.net_revenue_usd_m`. The consensus anchor 91,690 is 2,978 below the actual and scores 0; a 20.5% model gets 0.445; only a 21.5%+ bull case approaches 0.9. The field is derivable as an estimate, but the tolerance does not make the forecast method-only.

**No leak found:** every XBRL fact with `end_date=2026-03-31` has `available_at_s=21731`; pre-3300 documents are only the 10-K, the 2026-04-02 8-K (controller resignation) and the 2026-04-10 8-K (executive awards) — no Q1 2026 operating data. The 2026-04-29 close is at t=3600, after the forecast deadline. Peer earnings (MSFT 3811, META 3941, AMZN 4735, AAPL 91841) are after 3300. The reference forecast uses only t=0 data.

---

## 6. Timing feasibility

The cost model is `catalog=5s`, `query=15s`, `read=10s`, `submit=10s`, `wait=0s` (but wait consumes one action). The reference uses 16 actions; a solution with 30–50 actions is still well inside the 120 budget.

| Phase | Window | Reference actions | Reference submit | Slack |
|---|---|---:|---:|---:|
| Forecast | t=0 … 3,300 | 8 (read manual + 4 queries + 10-K read + price query + submit) | 105 | 3,195 s |
| Reconciliation | t=3,695 … 4,800 | 2 (read 8-K + submit) | 3,715 | 1,085 s |
| Verification | t=21,731 … 22,800 | 3 (read 10-Q + read 8-K + submit) | 21,761 | 1,039 s |
| **Total** | shift 0 … 23,400 | **16** | **21,761** | **1,639 s to shift end** |

A competent solver can afford extra catalog/query/read steps before each deadline: e.g., 40 actions × ~12 s average = ~480 s. The only timing trap is reading the 8-K at t=3600 (the market-update release) instead of waiting to t=3695; that read fails and the audit penalty is 0.25. The reference waits twice (3600, then 3695). This is avoidable but worth documenting.

**Verdict on timing:** no blocker. The 120-action budget is ample; all three deliverables are reachable with >1,000 s slack.

---

## 7. Manual / schema / judge consistency

| Area | Finding | Severity |
|---|---|---|
| Required payload fields | Every field accepted by `validate_submission` is derivable at the stated time except forecast EPS. | **Blocker (EPS)** |
| Judge check ↔ manual | Each deterministic check maps to a manual requirement (forecast, reconciliation, verification, deadlines, source visibility). | OK |
| Post-deadline information | Reconciliation uses the 8-K at 3695 (< 4800); verification uses the 10-Q at 21731 (< 22800); audit checks publication at submission. The forecast checks score against post-release actuals, but the solver is not required to *read* them. | OK mechanically; **calibration blocker** |
| Units | USD millions, EPS USD, margins in percent/percentage points; all consistent. | OK |
| Hidden tolerances | The manual does not state the judge's 1,420.02 / 0.30 / 1.0 / 0.01 / 0.05 tolerances. A solver cannot calibrate to them; the design doc's "±1.5% / ±0.30" is only a partial hint. | Major (fairness) |
| Narrative fields | Forecast has `basis`; reconciliation and verification have **no documented** narrative field. The engine accepts an undocumented `summary`, but the manual/TOOLS never mention it. E2/E3/E4/L4 need narrative locators. | **Blocker (rubrics)** |
| Consensus basis | Manual and `consensus.csv` say 91,690 is **net of TAC**; the design doc calls it **total revenue** and recommends 82,500–83,000 net. Following the design doc yields 0 on forecast revenue. | **Major** |
| GS margin ground truth | Ground truth 45.2817 vs exact 45.2815 (40,589/89,637). The 0.05pp tolerance gives 0.996, so `tenq` cannot reach 1.0. | Minor |
| Design weights | Design says reconciliation weights 5/5/5/5 and beat/miss 2.5/2.5; judge uses 3/3/3/3 and 2/2/2/2. Design says segment margin tolerance 0.1pp; judge 0.05pp. | Minor/major (misleading) |
| Design budget | Design §6 says 160 actions; scenario/manual/task say 120. | Minor |
| TAC rate | The 10-Q says TAC rate 19.7% (on a mix-shift basis); the 10-K TAC/advertising rate is 20.34%; TAC/total revenue is 13.9%. The manual defines net revenue as total − TAC but not the TAC-rate denominator. A forecast using 19.7% × total revenue overstates TAC and understates net revenue. | Minor (forecast modeling) |
| Segment margin source | The 10-Q extract has no segment operating income; margins are only in the EX-99.1 segment table. The manual says "segment margin" but not which document. | Minor |
| Doc id mapping | CSV doc ids are `000043_ex99_1` etc.; the DB/API ids are `googl-8k-20260429-ex991`. A solver citing the CSV id gets an unknown-doc audit penalty (0.15). The data service's `documents` table is the source of truth. | Minor |
| 8-K timing trap | The 3,600 release is the 4/29 close (market update), not the 8-K; the 8-K is 3,695. A read at 3,600 fails and incurs 0.25 audit penalty. | Minor/fairness |
| Failed-read penalty | The manual says citations must be published, but does not warn that a failed read of an unpublished doc is journal-penalized 0.25 (cap 0.5). A cautious solver exploring early loses points. | Minor/fairness |
| Segment op income | Verification's segment margins require the release table; a solver reading only the 10-Q cannot fill them. The reference cross-checks both and notes the presentation difference, which is good for L4. | Minor |

No check requires information that is only published *after its own deadline* for the reconciliation/verification/tenq/timeliness/audit checks. The forecast checkpoint is different: it is scored against an outcome that is not derivable at its deadline. That is the core calibration defect.

---

## 8. Rubric review (E1–E4, L1–L4)

The LLM rubric checks were **not executed** (no judge model/harness in this review). The assessment below is a static review of the reference submission's `summary`/`basis` text against the exact criteria in `judge/rubric_evidence.json` and `judge/rubric_logic.json`.

| Criterion | Reference evidence | Assessment | Ambiguity / risk |
|---|---|---|---|
| **E1** source doc ids real and published; EX-99.1 cited | Reconciliation cites `googl-8k-20260429-ex991`; verification cites `googl-8k-20260429-ex991` + `googl-10q-20260331`; both published at their submission times. | Pass | CSV-vs-DB doc-id mapping is a trap; the DB ids are the right ones. |
| **E2** traceable locators, ≥2 attributed data points, no contradiction | Reconciliation summary names "Consolidated Statements of Income" and the revenue/cost/TAC/operating income/net income/EPS line items; verification names "Consolidated Statements of Income" and "MD&A Cost of Revenues"; values match the documents. | Pass (likely) | "Locators" is not defined (section? table row? line number?); a strict judge may want exact row labels. The `summary` field is undocumented. |
| **E3** net revenue = total revenues − TAC, both attributed; not asserting an issuer-printed net revenue | Reconciliation: "Net revenue is not printed by the issuer: $109,896M total revenues − $15,228M TAC = $94,668M." Verification repeats the derivation. | Pass | None; the reference explicitly says the issuer did not print it. |
| **E4** release-vs-10-Q comparison, explicit match, names GAAP line/statement | Verification: "Form 10-Q Consolidated Statements of Income: Revenues $109,896M; Income from operations $39,696M; Net income $62,578M; Diluted net income per share $5.11… All three GAAP lines (revenue, operating income, diluted EPS) match the release; consistency = true." | Pass | None. |
| **L1** forecast combines consensus with observable pre-release info; explains difference from consensus | Basis cites consensus 91,690/2.76, XBRL revenue history, 10-K TAC/advertising, equity-gain history, 4/28 close; model net +2.4% vs consensus, EPS 3.25 vs 2.76. | Pass | The difference is explained numerically; no segment-mix detail, but the rubric allows "historical revenue/TAC structure, segment mix, market data or disclosed guidance" (any). |
| **L2** probabilities internally consistent with forecast/uncertainty | 0.75/0.75 for a +2.4% net-revenue and +17.8% EPS forecast; no contradictory statement. | Pass (arguable) | The basis does not explicitly pair "implied surprise" with "matching probability"; a strict judge may want a sentence like "a +2.4% beat is ~75% likely." The reference's summary is silent on the probability rationale. |
| **L3** reconciliation derives surprise % and beat/miss from own actuals and frozen consensus, correct arithmetic | Summary gives 3.2479% and 85.1449%, and both beats; arithmetic is correct. | Pass | None. |
| **L4** one concrete case-specific cross-check/caveat | Verification: "Segment margins, only in the release segment table" and the three-line GAAP match; this is a concrete presentation difference. | Pass | None; "only in the release segment table" is exactly the kind of case-specific caveat L4 wants. |

**Rubric verdict:** a good-faith solution can satisfy E1–E4/L1–L4 **if it uses the undocumented `summary` field**. A solver restricted to the documented payload schemas cannot include the locators/derivation narrative and is likely to fail E2/E3/E4/L4, losing up to 15 points. That alone can drop a perfect deterministic solution below 0.95. The fix is to document `summary` (or add a `basis`/`evidence` field to every payload) in `desk/manual.md` and the controller `TOOLS` text.

---

## 9. Ambiguities and fairness risks

**Blockers**

1. **Forecast EPS is an oracle field.** The target 5.11 includes a $2.35 one-time equity-securities gain ($36.9B pre-tax) disclosed only in the 8-K EX-99.1 footnote at t=3695 and the 10-Q note at t=21731. Consensus is 2.76; a defensible forecast is 2.7–3.6, which scores 0 against the 0.30 tolerance. The maximum defensible full-case score is ~91.99, below 0.95. This is not a "hard" check; it is unearnable from the right-time information.
2. **Narrative field is undocumented.** E2/E3/E4/L4 require source locators and derivation text; only the forecast `basis` is documented. The engine accepts `summary`, but the manual/TOOLS do not mention it. A solver using only documented tools loses up to 15 rubric points.

**Major**

3. **Design-doc consensus contradiction.** The design doc calls 91,690 "total revenue" and recommends a forecast net revenue of 82,500–83,000 (subtracting TAC again). The manual and `consensus.csv` say 91,690 is **net of TAC**; the judge expects ~94,668. A solver who follows the design doc scores 0 on forecast revenue.
4. **Forecast revenue tolerance is not "generous."** The actual +3.25% beat is outside a consensus-anchored model; a defensible 20.5% model scores 0.445; a 21.5% bull scores 0.907. The design's ±1.5% is a narrow band around an unknowable print. The forecast is effectively a point prediction of the actual beat, not a method test.
5. **Hidden tolerances.** The manual never states the judge's tolerances (1,420.02 net revenue, 0.30 EPS, 1.0/0.01 reconciliation, 0.05/0.5 surprise, 0.05pp margins). A solver cannot calibrate; the design doc's hints are partial and partly wrong (weights, 0.1pp margin, budget 160).

**Minor**

6. **GS margin ground truth typo.** 45.2817 vs 45.2815; `tenq` max 0.9996, so the check can never "pass" at the judge's 0.999999 threshold. The aggregate loss is 0.006/100, but the per-check outcome is "fail" even for a perfect answer.
7. **TAC-rate ambiguity.** 19.7% (10-Q mix-shift), 20.34% (10-K TAC/advertising), 13.9% (TAC/total revenue). A forecast using 19.7% × total revenue overstates TAC by ~6,000 and scores 0 on net revenue. The manual should define the denominator or provide the historical TAC table.
8. **Segment-margin source.** The 10-Q extract has no segment operating income; only the EX-99.1 segment table has it. A solver reading only the 10-Q cannot fill `segment_margins_pct`; the manual should say the release is the source.
9. **Doc-id mapping.** CSV ids (`000043_ex99_1`) differ from DB/API ids (`googl-8k-20260429-ex991`). A solver citing the CSV id gets an unknown-doc audit penalty (0.15). The DB `documents` table is the source of truth; this should be stated.
10. **8-K timing trap.** The 3,600 release is the 4/29 close, not the 8-K; the 8-K is 3,695. A solver who reads at 3,600 gets a failed read and a 0.25 audit penalty. The manual should state the release sequence or the controller should surface the next *document* release separately.
11. **Failed-read penalty is not documented.** A cautious solver exploring the 10-Q early (before 21,731) loses 0.25 per failed read (cap 0.5). The manual only says citations must be published; it does not warn that exploratory reads are penalized.
12. **Design-doc weights/tolerances/budget** (5/5/5/5 vs 3/3/3/3; 2.5/2.5 vs 2/2/2/2; 0.1pp vs 0.05pp; 160 vs 120) are inconsistent with the judge. They are not solver-visible in the environment, but they mislead case maintainers and any reviewer using the design as the spec.
13. **Forecast total/TAC are not scored directly.** Only net revenue and EPS are scored; a solver could submit inconsistent total/TAC components and still score. The rubric E3 checks the net derivation, but the deterministic check does not. This is a scoring gap, not a fairness issue.
14. **The 10-Q is a selected-section extract.** It has no full notes/EPS note and no $36.9B footnote; the one-time gain explanation is only in the release. The verification check only asks whether the release matches the 10-Q, so this is not a blocker, but a solver cannot reconcile the EPS surprise from the 10-Q alone.

---

## 10. Fixes

**P0 — required for a passable case**

1. **Fix forecast EPS.** Score **core EPS excluding one-time equity-securities gains** (target 2.76), or explicitly provide a pre-release signal for the Q1 2026 gain, or widen `forecast_eps` tolerance to cover 2.76–5.11 (e.g., ≥2.5) and document it. The current 0.30 tolerance around 5.11 is unearnable. If the case wants GAAP 5.11, add an observable pre-release event (e.g., a portfolio-company IPO/valuation event at t<3300) so a good-faith analyst can forecast it.
2. **Document the narrative field.** Add `summary` (string, ≤ some length) to the reconciliation and verification payload schemas in `desk/manual.md` and the controller `TOOLS` text, or add a `basis`/`evidence` list to every payload. Without this, E2/E3/E4/L4 are not earnable from documented tools.
3. **Correct the design doc.** State that 91,690 is **net of TAC**, not total revenue; remove the 82,500–83,000 reference path (it scores 0); align the design's weights (3/3/3/3, 2/2/2/2), margin tolerance (0.05pp), and budget (120) with the judge; state that the forecast is a point prediction, not only a method test.
4. **Fix the GS margin ground truth.** Use 45.2815 (or 45.281524) instead of 45.2817, and add a unit test that a perfect submission scores 1.0 on every deterministic check. This removes the 0.9996 ceiling and the per-check "fail" outcome.

**P1 — calibration/fairness**

5. **Widen or reweight forecast revenue.** Either widen the net-revenue tolerance to ~±3% (2,840) so a defensible 20.5–21.5% model gets meaningful credit, or provide a pre-release Cloud backlog/guidance signal, or reduce forecast_revenue's weight. A 20.5% model scoring 0.445 is a method penalty, not a knowledge test.
6. **Define the TAC rate.** State that TAC is modeled as a percentage of Google advertising revenue (10-K: 20.34%; 10-Q mix basis: 19.7%), not total revenue; provide the historical TAC table. This prevents a ~6,000 TAC error.
7. **State the segment-margin source.** The release segment table is the only source of segment operating income; the 10-Q extract lacks it. Add this to the manual.
8. **Document the release sequence and failed-read penalty.** Say the 3,600 release is the close, the 8-K is 3,695; say that reading an unpublished doc is journal-penalized 0.25 (cap 0.5) and that `documents.doc_id` are the API ids, not the CSV ids. Consider removing the failed-read penalty for exploratory reads, or making `read` return a clear "not yet published; next release at t=…" without penalty.

**P2 — polish**

9. Add the judge's tolerances (or a sensitivity note) to the manual so solvers can calibrate.
10. Add a free-text leak check: the deterministic audit does not inspect `basis`/`summary` for future data. A cheating solver could write actuals into the text; the numeric checks are time-gated, but the rubric judge may be fooled. At minimum, review the text for post-cutoff figures.
11. Reconcile the design doc's §6 budget (160) and §11 scoring claims with the actual task (120 actions, point-prediction forecast).
12. Add a judge unit test for the GS margin, the surprise arithmetic, and the `pick_submission` boundary (submission exactly at the deadline).

---

## 11. Exact commands and artifacts

Run from `<repo>`:

```bash
# 1. Build and export the reference evidence (16 actions)
python3 <workdir>/refsol/run_reference.py --variant base --out <workdir>/refsol/evidence.json

# 2. Put it where the judge expects it
rm -rf <workdir>/refsol/submission
mkdir -p <workdir>/refsol/submission/evidence
cp <workdir>/refsol/evidence.json <workdir>/refsol/submission/evidence/equity_event.json

# 3. Run all seven deterministic checks
for c in forecast_revenue forecast_eps probabilities reconciliation_actuals \
         tenq_verification timeliness audit_integrity; do
  python3 tasks/equity-event-001/judge/verify_ingest.py \
    --scenario tasks/equity-event-001/judge/ground_truth.json \
    --submission <workdir>/refsol/submission \
    --result <workdir>/refsol/result_${c}.json \
    --check "$c"
done
```

`verify_ingest.py` writes each result to `--result` and prints nothing on success. The result files are `<workdir>/refsol/result_<check>.json`; the weighted total was computed as:

```python
weights = {'forecast_revenue':12,'forecast_eps':8,'probabilities':10,
           'reconciliation_actuals':20,'tenq_verification':15,
           'timeliness':10,'audit_integrity':10}
total = sum(json.load(open(f'<workdir>/refsol/result_{c}.json'))['score'] * w
            for c, w in weights.items())
# total = 70.020348 / 85 = 0.823769; +15 rubrics = 85.020348 / 100
```

**Reference artifacts**

| Artifact | Path |
|---|---|
| Reference harness | `<workdir>/refsol/run_reference.py` |
| Exported evidence | `<workdir>/refsol/evidence.json` |
| Submission copy | `<workdir>/refsol/submission/evidence/equity_event.json` |
| Per-check results | `<workdir>/refsol/result_forecast_revenue.json`, `result_forecast_eps.json`, `result_probabilities.json`, `result_reconciliation_actuals.json`, `result_tenq_verification.json`, `result_timeliness.json`, `result_audit_integrity.json` |
| Variant results | `<workdir>/refsol/result_{consensus,bull,eps_partial,oracle}_<check>.json` |
| Machine-readable summary | `<workdir>/refsol/summary.json` |
| Run logs | `<workdir>/refsol/run_base.log`, `run_consensus.log`, `run_bull.log`, `run_eps_partial.log`, `run_oracle.log` |

**Reference evidence highlights**

- `actions_used`: 16; `business_time_s`: 21,761; `submission_times`: forecast 105, reconciliation 3,715, verification 21,761.
- Forecast: total 108,731.97; TAC 14,852.218; net 93,879.752; EPS 3.25; probabilities 0.75/0.75.
- Reconciliation: 109,896 / 15,228 / 94,668 / 5.11; consensus 91,690 / 2.76; surprises 3.2479% / 85.1449%; both beat; source `googl-8k-20260429-ex991`.
- Verification: 109,896 / 15,228 / 94,668 / 39,696 / 36.1214 / 62,578 / 5.11; consistency true; GS 45.2815; GC 32.9439; sources `googl-8k-20260429-ex991`, `googl-10q-20260331`.
- Audit: 1.0, no penalties; no unknown/early citations; no failed reads/submits.

---

## 12. Limitations

- **Rubric checks were not executed.** There is no LLM judge invocation in this review. The "full case" 85.02/100 assumes all eight rubric criteria are awarded. The deterministic 82.38% is the measured result. If the LLM judge is strict on E2 (exact locators) or L2 (probability rationale), the full-case score could be lower. The static review in §8 is the basis for the "likely pass" assessments.
- **One reference path.** The reference chooses a 20.5% growth / 3.25 EPS model. A different good-faith analyst might choose 21.5% / 3.60 (full case 90.68) or 19.5% / 2.90 (lower). The conclusion is robust: every defensible EPS is far below 4.923, so no reasonable path reaches 0.95.
- **The design doc is not solver-visible.** It is a case-authoring artifact, not part of `environment/initial_workspace`. The manual is the solver-visible spec; the design inconsistencies are still important for maintainers and for the case's stated intent.
- **The judge is deterministic.** The `tenq` 0.9996 is a ground-truth rounding artifact, not a model error. The aggregate uses the score; the per-check `outcome` is strict.
- **No repo files were modified** except this report. The harness and evidence are under `<workdir>/refsol/`.

---

## Appendix A — Per-check result JSON (base)

```
forecast_revenue      score=0.444904  outcome=fail  weight=12  contrib=5.3388
forecast_eps          score=0.000000  outcome=fail  weight= 8  contrib=0.0000
probabilities         score=0.968750  outcome=fail  weight=10  contrib=9.6875
reconciliation_actuals score=1.000000 outcome=pass  weight=20  contrib=20.0000
tenq_verification     score=0.999600  outcome=fail  weight=15  contrib=14.9940
timeliness            score=1.000000  outcome=pass  weight=10  contrib=10.0000
audit_integrity       score=1.000000  outcome=pass  weight=10  contrib=10.0000
det sum 70.020348 / 85  mean 0.823769
full case with rubrics 15.0: 85.020348 / 100  mean 0.850203
```

## Appendix B — Reference forecast basis (verbatim)

```
Frozen consensus (consensus_estimates, available t=0): Q1 2026 revenue net of TAC $91690.00M (+20.0% YoY) and GAAP diluted EPS $2.76; as of 2026-03-17, Zacks via O19.
Visible XBRL quarterly revenue: Q1 2025 $90234M, Q2 $96428M, Q3 $102346M, Q4 $113828M; YoY growth 12.0% -> 13.8% -> 15.9% -> 18.0%, OLS trend next quarter 20.0%.
FY2025 10-K (googl-10k-20251231, available t=0): TAC $59926M on Google advertising revenue $294691M = 20.34% TAC rate; Q1 TAC is 22.4% of FY2025 cost of revenues, so Q1 2025 TAC is estimated at $13406M and Q1 2025 net revenue at $76828M.
Model: Q1 2026 total revenue +20.5% to $108732.0M; advertising +12.5% to $74261.1M; TAC 20.0% of advertising = $14852.2M; net revenue = $108732.0M - $14852.2M = $93879.8M (2.4% vs consensus).
EPS: consensus $2.76 plus ~1.4% buyback to $2.80 core, plus ~$0.45 expected normal equity-securities gain (FY2025 gain $24.08B; Q1 2025 $9.96B), = $3.25 GAAP. No Q1 2026 operating or investment data are published before 15:55 ET.
Visible prices: latest close $349.78 on 2026-04-28, +3.7% over the prior five sessions; no guidance or Q1 2026 operating data are published before 15:55 ET.
Base case: trend + 0.5pp AI/Cloud lift; TAC at 20.0% of advertising revenue.
```

The forecast text contains no actual Q1 2026 figures (5.11, 109,896, 94,668, 36.9B, 2.35) or post-3300 doc ids. The reconciliation/verification summaries are in `<workdir>/refsol/evidence.json` and use only the 8-K/10-Q.
