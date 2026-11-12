# equity-event-001 — scoring audit for v3.3.1 refactor

Status: audited before any change. Scope: `tasks/equity-event-001/`, plus the
platform aggregation semantics that consume its checks. No platform code was
modified.

## 1. Current scoring formula and weights (v1.3.1)

`task.toml` defines nine checks aggregated by `weighted_mean` with
`pass_threshold = 0.85`; no check has `must_pass = true`:

| check | type | weight | current implementation |
|---|---|---|---|
| forecast_composite | command | 74 | mean of 9 per-metric `linear(pred, actual, tol)` |
| probabilities | command | 5 | `max(0, 1 - mean((p - 1)^2) / 2)` over two "true" events |
| one_off_analysis | command | 3 | mean of `linear` for equity gain and core EPS |
| reconciliation_actuals | command | 3 | 20 internal points: 4 actuals x3, 2 surprise x2, 2 beat/miss x2, /20 |
| tenq_verification | command | 2 | 10 items: 7 GAAP + margin + 2 segment margins + bool claim, /10 |
| timeliness | command | 1 | fraction of 3 phases submitted by deadline |
| audit_integrity | command | 2 | 1.0 minus citation/read/submit penalties (global read set) |
| evidence_chain | llm_rubric | 5 | rubric_evidence.json: E1–E4, weight 1 each |
| analysis_logic | llm_rubric | 5 | rubric_logic.json: L1–L4, weight 1 each |

Platform aggregation (`goldtrace/liteeval/domain/benchmark.py`): score is the
weighted mean of per-check scores; `pass` requires every `must_pass` check to
pass and `score >= pass_threshold`; a failed gate forces the reported score to
0.0 while `before_gate` keeps the raw value. With no `must_pass` check the
threshold only affects the `outcome` label, not the numeric score. JSON
verdicts must carry `schema_version`, `check_id`, `outcome`, `reason` and a
numeric `score` in [0,1].

## 2. Observed score decomposition (r13–r15, v1.3.1)

| component | max | r13 | r14 | r15 |
|---|---|---|---|---|
| forecast_composite | 74 | 18.20 | 7.62 | 11.35 |
| probabilities | 5 | 4.43 | 4.31 | 4.46 |
| one_off_analysis | 3 | 3.00 | 3.00 | 3.00 |
| reconciliation_actuals | 3 | 2.98 | 2.98 | 2.98 |
| tenq_verification | 2 | 1.97 | 1.97 | 1.97 |
| timeliness | 1 | 1.00 | 1.00 | 1.00 |
| audit_integrity | 2 | 2.00 | 2.00 | 2.00 |
| evidence_chain | 5 | 2.50 | 3.75 | 3.75 |
| analysis_logic | 5 | 2.50 | 2.50 | 2.50 |

Total 38.61 / 29.13 / 33.01. Above 15 points of every run are earned by steps
that carry no real discrimination for this model (post-release copying,
compliance, a no-informed 0.5/0.5 probability pair still scoring ~0.875).
Forecast accuracy is the only component with a real spread.

## 3. Correctness bugs and validity problems found

1. **Probabilities floor.** `1 - Brier/2` maps the no-skill 0.5/0.5 forecast to
   0.875 because Brier is capped below 1 by construction. The check therefore
   rewards a maximally uninformative answer. The two events are also assumed
   `true` in code, and there is no test for worse-than-baseline predictions.
2. **EPS target inconsistency.** The forecast point estimate is
   `diluted_eps_ex_oneoffs_usd` (core EPS 2.76) while `eps_beat` is currently
   defined on reported GAAP diluted EPS, which includes an unknowable $36.9B
   equity-securities gain (GAAP EPS 5.11). A pre-release agent could not have
   forecast that beat from available evidence.
3. **Audit uses a session-global read set.** `read_documents()` collects every
   successful read without timestamps, so a document read *after* a submission
   (or after its deadline) still legitimises a citation made earlier. Reads of
   documents that were unavailable at the time of the submission are only
   caught through a second, publication-time check.
4. **Reconciliation does not validate the submitted consensus.** Surprise and
   beat/miss are compared directly with ground-truth labels, so a candidate
   that submits a wrong consensus can still collect full credit on the
   surprise labels; nor is surprise recomputed from the candidate's own
   numbers.
5. **10-Q verification partly trusts a self-report.** One of ten points is the
   candidate's boolean `press_release_matches_10q`, which is a claim, not
   evidence. The remaining values are checked against authoritative filed
   values, which are identical across release and 10-Q for the consolidated
   lines, so independent release-vs-10-Q comparison is limited to the values
   that the schema carries (documented as a limitation below).
6. **Forecast composite has no internal consistency check.**
   `TotalRevenue - NetRevenue - TAC` is not validated, although it is exactly
   the relation the task asks the agent to model.
7. **Citable-document set is incomplete.** Peer filings are visible in the DB
   and can be legitimately read and cited for read-through commentary, but
   they are absent from `ground_truth.documents`, so the audit marks such
   citations "unknown".
8. **Rubrics inconsistent with the current task.** Rubric metadata still says
   "v2"; E3/L1 text describes a 9-metric model but criteria were written for a
   smaller task; there is no handover rubric even though the verification
   stage requires a substantive summary; criteria are all weight-1 binary with
   no distinction between factual compliance and analytical quality.

## 4. Existing-format compatibility for proposed changes

| proposed criterion | existing field / evidence source | change needed |
|---|---|---|
| forecast consistency | `forecast.{total_revenue_usd_m,net_revenue_usd_m,tac_usd_m}` | none (verifier only) |
| probability skill score | `forecast.probabilities.{net_revenue_beat,eps_beat}` + truth event outcomes | ground_truth definition update only |
| per-submission audit | evidence `journal[].{at_s,action,ok,doc_id}` + `submissions[phase][].at_s` + truth `documents` | none (verifier only) |
| consensus validation | `reconciliation.consensus.{net_revenue_usd_m,diluted_eps_usd}` | none |
| surprise from own consensus | `reconciliation.actuals`, `reconciliation.consensus`, `reconciliation.surprise` | none |
| 10-Q value verification | `verification.gaap`, `verification.segment_margins_pct`, `verification.one_off`, truth actual | none |
| evidence rubric E1–E6 | `journal` reads, `basis[].{source_doc_id,note}`, `source_doc_ids`, summaries | none (rubric only) |
| logic rubric L1–L5 | forecast payload + reconciliation/verification payload + summaries + truth | none (rubric only) |
| handover rubric H1–H5 | `submissions.verification[].summary` + forecast/reconciliation payloads + truth | none (rubric only) |

No new submission field is required and no engine/controller/database change
is needed; the verifier already receives journal entries with business-clock
timestamps, document ids and success flags, and every rubric criterion maps to
text or numbers the candidate already submits.

## 5. Ground-truth and financial-definition issues

- **Core EPS methodology is not documented.** Needed: which one-off is
  excluded, whether it is tax-effected, the tax effect used, the diluted share
  count basis, rounding, and the fact that this is a project-defined
  analytical metric rather than a company-reported figure. Source values:
  GAAP diluted EPS 5.11, pre-tax equity-securities gain 36,915, tax effect
  8,200, after-tax gain 28,700, implied EPS impact 2.35, core EPS 2.76 (2 dp).
- **Probability outcome definitions must be explicit.** Current truth sets
  both events to `true`; `beat_miss` and `surprise_expected` are computed on
  reported GAAP figures while the point forecast is core EPS.
- **Release vs 10-Q comparison limit.** Both documents report identical
  consolidated values for total revenue, TAC, net revenue, operating income,
  net income and diluted EPS, which is why verifying the submitted values
  against the authoritative filed values also verifies 10-Q agreement for those
  lines. Segment operating income appears only in the earnings release, so the
  segment-margin items cannot be corroborated from the 10-Q as provided. This
  limitation will be documented rather than hidden.

## 6. Proposed changes

| change | expected effect |
|---|---|
| weights 55 / 5 / 2 / 2 / 2 / 1 / 2 / 10 / 13 / 8 | forecast remains the largest single check; extraction/compliance cap falls from 21 to 9 points; analysis-quality checks can carry real weight |
| probabilities -> BSS bounded at 0 | 0.5/0.5 scores 0, perfect scores 1, worse-than-baseline cannot score positive |
| EPS event on core-EPS basis (same basis as point forecast) | removes unknowable one-off from the probability event; truth outcome for `eps_beat` becomes false |
| audit per-submission timestamps | citations must be supported by a read that happened after publication and before that submission |
| reconciliation validates consensus + recomputes surprise from own inputs | wrong consensus cannot be hidden behind a correct final label |
| 10-Q: 9 value items, claim not scored | self-reported boolean no longer earns a point; values verified against filed truth |
| forecast consistency factor (0.9 metric mean + 0.1 accounting consistency) | internal inconsistencies reduce the composite; relation tolerance ±2.0 USD m |
| three rubrics (10/13/8) with binary factual + graded analytical criteria | separates compliance from analysis quality and adds handover assessment using the existing summary |
| ground-truth additions: core EPS methodology, probability event definitions, peer documents, release/10-Q limitation | removes ambiguity and makes every criterion checkable |

No criterion is added that depends on fields the submission schema does not
already contain. Lower scores alone are not evidence of improvement; the
report will argue validity per change.

## 7. Limitations recorded for the final report

- Single case family; three rollouts cannot establish population-level
  calibration.
- LLM-judge scores are stochastic; per-check variance will be reported.
- The judge-side dataset cannot perform a byte-level release-vs-10-Q diff; the
  10-Q check verifies authoritative values, not query behaviour.
- `--trusted-local` means evidence integrity relies on the controller freeze;
  audit checks detect unsupported citations, not deliberate tampering outside
  the harness.
- Model pretraining knowledge about the event remains an uncontrolled risk,
  mitigated by the real publication schedule and audit rules but not removed.

## 8. Implementation status (2026-11-12)

All eight audit findings were implemented in the bench case; no platform code
was modified. Summary of what shipped:

- `judge/verify_ingest.py` v1.4.0: BSS probability score, per-submission audit
  with `available_at <= read_at <= submission.at_s`, reconciliation that
  validates the candidate's own consensus and recomputes surprise/beat, 10-Q
  check over nine reported values (the self-reported boolean is recorded but
  not scored), forecast accounting-identity term, peer-document support,
  empty-run audit = 0, rounding fixes.
- `judge/ground_truth.json`: `eps_beat` re-defined on the core-EPS basis
  (`net_revenue_beat: true`, `eps_beat: false`), explicit
  `probability_event_definitions`, `core_eps_methodology`,
  `tenq_verification_note`, `audit_semantics`, peer documents and the new
  weight table.
- `task.toml`: ten checks weighted 55/5/2/2/2/1/2/10/13/8, all
  `must_pass=false`, `pass_threshold 0.85`, `judge_timeout_seconds 480`
  (three sequential LLM judge calls measured 137-201 s; 180 s caused a
  timeout in one run).
- Three LLM rubrics: `rubric_evidence.json` (E1-E6, 10), `rubric_logic.json`
  (L1-L5, 13), new `rubric_handover.json` (H1-H5, 8, verification summary
  only).
- `desk/manual.md`: core-EPS definition, probability-event basis, per-stage
  audit rules, v3.3.1 weight table, handover guidance.
- `tests/test_equity_event_judge.py`: 23 offline tests, all passing.
- `dataset.toml` 1.4.0 (validate valid, task_count 8). Canonical digest must be
  computed from a clean `git archive HEAD` export: the platform loader hashes
  every repository file, so a digest stored inside the repo would invalidate
  itself; release identity is the dataset version plus the git commit.

Verification results: scripted-oracle conformance 0.94 pass
(execution `107829de4a134171893a043b472a85e8`), empty negative baseline 0.0
(`f0231ef59c8f47459304882d8fec4d24`), and six scored real-model rollouts
(mean 43.14, sd 5.61; final configuration mean 42.01, sd 1.50). Applying the
v1.3.1 weights to the same evidence gives mean 36.40 (final four: 34.92),
which shows the score shift comes from weight reallocation, not from a model
capability change. Details, per-check tables, judge-variance measurements and
remaining limitations are in
`docs/reports/equity-event-001-v3.3.1-report.md`.
