# fin-stream-decision-bench

**A single-case benchmark for AI agents making timely, auditable decisions over a continuously updating financial data stream.**

The shipped case is **`equity-event-001`**: an on-duty equity research analyst covering **Alphabet's Q1 2026 earnings night** (2026-04-29, 15:00–21:30 ET). The agent works inside a SQLite database in which every row carries a real publication time (`available_at_s`); the tool layer builds a filtered view for the current business time, so the future does not exist yet. Documents (10-K, 8-K, 10-Q) are served only after their real SEC acceptance time, and every read/citation is audited.

> **Distribution note (v1.4.1):** this repository intentionally contains only `equity-event-001`. The other task families of the parent benchmark (LDI duty, treasury network, source-treasury reconstruction) are still under development in the author's internal question bank and are **not distributed here**; earlier revisions of this repository included them, and the v1.4.1 history entry marks their removal.

## The case in one shift

| Phase | Deadline (business time / ET) | Deliverable |
| --- | --- | --- |
| **Forecast** — before the earnings 8-K | t = 3,300 s / 15:55 | Nine-metric point forecast: total revenue, net revenue, TAC, Google Services revenue, Google Cloud revenue, Services operating income, Cloud operating income, consolidated operating income, and diluted EPS excluding one-offs; plus beat/miss probabilities and a basis |
| **Reconciliation** — after the 8-K release (t = 3,695 s / 16:01) | t = 4,800 s / 16:20 | Actuals, surprise vs. frozen consensus computed from the candidate's own consensus, beat/miss classification, source doc ids |
| **Verification** — after the 10-Q (t = 21,731 s / 21:02) | t = 22,800 s / 21:20 | Verify release vs. 10-Q, bridge GAAP EPS to core EPS through the $36.9B one-off equity-securities gain, segment margins, and a handover summary |

The agent gets 120 actions (query 15 business seconds, read 10, catalog 5, submit 10) and must keep an auditable trail. The controller replays a business clock; model thinking time does not advance it. See `tasks/equity-event-001/environment/initial_workspace/desk/manual.md` for the tool protocol and payload schemas.

## Scoring (v1.4.0, 100 points, no `must_pass` gate)

| Check | Weight | Type |
| --- | ---: | --- |
| `forecast_composite` (9 metrics + accounting-identity term) | 55 | deterministic |
| `probabilities` (bounded Brier Skill Score: 0.5/0.5 → 0; better-than-50% baseline required for positive credit) | 5 | deterministic |
| `one_off_analysis` (equity gain + core EPS) | 2 | deterministic |
| `reconciliation_actuals` (validates submitted consensus; recomputes surprise/beat) | 2 | deterministic |
| `tenq_verification` (nine reported values; self-reported `matches_10q` not scored) | 2 | deterministic |
| `timeliness` (three phases on time) | 1 | deterministic |
| `audit_integrity` (per-submission timestamps, reads, unpublished citations) | 2 | deterministic |
| `evidence_chain` (E1–E6) | 10 | `llm_rubric` |
| `analysis_logic` (L1–L5) | 13 | `llm_rubric` |
| `handover_quality` (H1–H5, grades the verification-stage summary) | 8 | `llm_rubric` |

`pass_threshold` is **0.85**; a single failed check never zeros the whole task. Deterministic checks run as an offline command judge over the frozen evidence (`tasks/equity-event-001/judge/verify_ingest.py`); the three LLM-rubric items are validated by the platform and aggregated per criterion — they account for 31/100 and are the only stochastic part (≈ ±1.5 pp on the total per re-judge).

## Calibration

With **`deepseek-flash`** (6 scored rollouts, identical package/harness/settings): **53.62 / 37.16 / 43.15 / 43.32 / 41.41 / 40.18** → mean **43.14**, sd **5.61** (final configuration four runs: mean 42.01, sd 1.50). Applying the previous v1.3.1 weights to the same evidence yields mean 36.40 — the shift comes from weight reallocation toward analytical evidence, not from loosening criteria.

Cross-model evaluation with the same task package and the same judge (three scored rollouts per model):

| Model | 3 scored rollouts | Mean ± sd |
| --- | --- | --- |
| `kimi-k3.1-pro` | 58.06 / 60.85 / 57.35 | **58.75 ± 1.85** |
| `glm-5.3` | 42.51 / 46.69 / 56.97 | **48.72 ± 7.44** |
| `deepseek-flash` | 50.45 / 43.01 / 47.03 | **46.83 ± 3.72** |
| `qwen3.8-max` | 45.39 / 44.09 / 44.19 | **44.56 ± 0.70** |
| `deepseek-v4-pro` | 30.94 / 31.82 / 34.69 | **32.48 ± 1.96** |

The spread concentrates in predictive skill and the three analysis-quality rubrics, not in the saturated compliance checks. **Caveats:** the rubrics were iterated on Flash traces and the judge is fixed to Flash, so scores are "under this rubric and this judge" rather than a general capability ranking; the GLM-5.3 Flash variants were not activated on the MaaS key (so `glm-5.3` was used); slow models brush the 2,400 s wall budget, and timeout failures are documented as infrastructure errors (the JSON-action harness HTTP timeout was raised from 180 s to 600 s, v1.3.1).

## Quickstart

Requirements: Python 3.11+ and **LiteEval ≥ `90ed715`** (the local-first agent evaluation backend).

```bash
# 1. Install the evaluation platform
git clone https://github.com/SephirahVII/LiteEval.git
cd LiteEval && python -m pip install -e .

# 2. Initialize the platform (one-time; interactive) and create a project + model connection
liteeval owner-init --username owner
#    Then create a project and a connection (console or API); note PROJECT_ID / CONNECTION_ID.

# 3. Register the workflow controller and the JSON-action agent harness
cd /path/to/fin-stream-decision-bench
liteeval harness workflows/equity-event-stream --project PROJECT_ID   # -> WF_REVISION
liteeval harness harnesses/json_action --project PROJECT_ID           # -> AGENT_REVISION

# 4. Validate, import and run the case
liteeval benchmark validate .
liteeval benchmark import . --project PROJECT_ID                     # -> RELEASE_ID
liteeval benchmark run RELEASE_ID --project PROJECT_ID \
  --agent-harness AGENT_REVISION \
  --workflow-harness WF_REVISION \
  --target-connection CONNECTION_ID \
  --judge-connection CONNECTION_ID \
  --trusted-local
```

- `--judge-connection` is required because the case contains `llm_rubric` checks; it may be the same model connection as the target.
- `--trusted-local` is required because the task uses the local `workspace` environment profile.
- Harness references are revision ids returned by `liteeval harness`; register once and reuse them.

Run the unit tests (no model calls, stdlib only):

```bash
python -m unittest discover -s tests -v
```

## Repository layout

```
dataset.toml                       benchmark manifest (single task)
tasks/equity-event-001/            task.toml, prompt.md, environment/initial_workspace
                                   (market.db + desk manual), workflow-fixtures/, judge/
                                   (ground truth, verify_ingest.py, three LLM rubrics, provenance/)
workflows/equity-event-stream/     harness.toml + controller.py + engine.py + data_service.py
harnesses/json_action/             community JSON-action agent harness (conversation continuation,
                                   reasoning passthrough, JSON/DSML action parsing)
tests/                             offline unit tests (judge edge cases, anti-leak scans)
docs/design/equity-event-stream-case-design.md   full case design (Chinese; DB, prompts, tools,
                                                 execution chain, rubric, judge prompts)
docs/validation/                   independent realism / anti-lookahead / solvability reviews
docs/reports/                      scoring-refactor report, cross-model report, rollout report
```

## Data, provenance and licenses

- **SEC EDGAR filings** — U.S. federal government works (public domain). Every document preserves its real `acceptanceDatetime`; HTML→text conversion is deterministic (no LLM) and numbers are byte-identical to the filing.
- **Yahoo Finance daily bars** — fetched from the public chart endpoint for research/benchmark use; redistribution may be subject to Yahoo's Terms of Service. Replace with a licensed market-data source for commercial redistribution.
- **Consensus snapshot** — Q1 2026 net-revenue `$91.69B` / EPS `$2.76`, quoted from the news document captured in *Investor's Last Exam* (O19; original source Zacks, as-of 2026-03-17). Cite ILE (arXiv:2610.38342) when reusing.
- Machine-readable provenance: `tasks/equity-event-001/data/PROVENANCE.json` and `tasks/equity-event-001/provenance/` (source URLs, SHA-256, capture scripts).
- **Code and benchmark content**: Apache-2.0 (see [`LICENSE`](LICENSE)); third-party data remains subject to upstream terms (see [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md)).

## Limitations

- The benchmark measures decision quality on a frozen business-clock replay, not real-time execution latency; model thinking time does not advance the business clock.
- Pretraining knowledge cannot be erased by access control. The case mitigates this by using facts empirically outside the tested models' memory and deterministic numeric tolerances; this remains a residual risk for other models.
- Runs use the trusted-local workspace profile: the evidence journal is a trust boundary, not a cryptographic proof. The verifier assumes controller-produced evidence is untampered (see the audit-integrity check and `docs/validation/`).
- LLM-rubric checks add sampling variance (≈ ±1.5 pp) and occasional stochastic judge errors; the platform marks such runs `unscored` rather than scoring them. Report repeat runs and `scoring_coverage`.

## Version history

- **v1.4.1 (single-case distribution)** — repository trimmed to the flagship case only: removed the LDI, treasury-network and source-treasury task packages, their workflow controllers and their design/calibration docs (still under development internally, not published); README, dataset manifest and provenance re-scoped to `equity-event-001`. Scoring unchanged from v1.4.0.
- **v1.4.0 (multi-model addendum)** — same v1.4.0 package evaluated on DeepSeek (Flash mean 46.83 ± 3.72; V4 Pro mean 32.48 ± 1.96) and Qianwen MaaS (qwen3.8-max 44.56 ± 0.70, glm-5.3 48.72 ± 7.44, kimi-k3.1-pro 58.75 ± 1.85); slow-model HTTP timeout raised (json_action 1.3.1); timeout/budget failures excluded and documented.
- **v1.4.0** — validity-first scoring refactor for `equity-event-001`: rebalanced weights (55 forecast / 31 analysis-quality rubrics), bounded Brier Skill Score, core-EPS probability event, per-submission audit, reconciliation self-consistency, 10-Q self-report removed from scoring, forecast accounting identity, new handover-quality rubric, `judge_timeout` 480 s, 23 offline tests; re-calibration on six rollouts (mean 43.14 ± 5.61) with a v1.3.1 counterfactual comparison. See `docs/reports/equity-event-001-v3.3.1-report.md`.
- **v1.3.1** — fixed the nine-metric forecast verifier (was averaging 7/9 metrics), re-ran three rollouts (38.61 % / 29.13 % / 33.01 %), updated the rollout report and design doc; open-source release (Apache-2.0, provenance, citation).
- **v1.3.0** — calibrated to the target band; nine-metric forecast promoted to the dominant weight (74/100); one-off bridge, peer-earnings noise, hardened audit and tighter LLM rubrics; harness hardened against protocol noise (JSON extraction + DSML parsing).
- **v1.2.0** — added `equity-event-001` (real SEC data, database time gating, deterministic + semantic judges) and `workflows/equity-event-stream`.
- **v1.0.0–v1.1.0** — original internal import and source-treasury metadata fixes (case families removed from the public distribution in v1.4.1).

## Citation

If you use this benchmark, please cite it via [`CITATION.cff`](CITATION.cff).

## Contributing

Issues and PRs are welcome — hardening of anti-lookahead audits, additional calibration runs and new cases (in the parent benchmark) are especially useful. Please keep the design constraints: iterate at the package level (the platform stays unchanged unless the package format genuinely cannot express something), keep deterministic judging for numeric criteria, do not mix scores across versions, and provide provenance for any new data.
