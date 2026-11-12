# fin-stream-decision-bench

**A benchmark for evaluating AI agents on timely, auditable decisions over continuously updating financial data streams.**

One case is one continuous duty shift. Market data, company filings, margin calls, payment notices and settlement instructions are released on a **business clock**; the agent must recognise risk, do quantitative reasoning, act and correct course **before each funding, payment and reporting window closes** — and leave an auditable trail that a judge can replay offline.

All figures, prices and documents in the benchmark come from real public sources (or from deterministic, reproducible simulations). A task is graded by an **independent offline command judge** that re-computes the frozen ledger/evidence — scores are reproducible, re-judgeable and versioned. Narrative criteria (only for the newest case family) use a `llm_rubric` judge whose per-criterion verdicts the platform aggregates deterministically.

## Why this benchmark

- **Time and state are first-class.** Information is only visible from its real publication time onward (`available_at_s` filtering on the database, not just a prompt instruction). Future materials cannot be pre-read; a correct analysis delivered after a deadline still fails.
- **Lookahead is tested, not assumed.** Every case ships an anti-lookahead audit: citing an unpublished document, a document you did not actually read, or a future filing is penalised deterministically.
- **Real data, real timestamps.** The flagship case is built from SEC EDGAR filings with their real acceptance timestamps, real Yahoo Finance daily bars and a frozen consensus snapshot.
- **Measured difficulty, validity-first scoring.** Case variants and weights are calibrated on measured model runs. The flagship case reports its full distribution rather than a single target band; the v1.4.0 scoring refactor prioritises construct validity (see `docs/reports/equity-event-001-v3.3.1-report.md`) and does not tune weights to hit a predetermined threshold.

## Case families

Current release covers **8 cases across 4 workflow controllers** (business-clock replay, deterministic settlement, offline judge):

| Family | Cases | What it tests | Status |
| --- | --- | --- | --- |
| LDI duty | `ldi-margin-001/002/003` | 08:30–11:00 treasury liquidity duty; two branches share the pre-09:12 event stream, then diverge into repo rejection vs normal, with a calm-state control for false alarms | process acceptance |
| Treasury network L8 | `treasury-duty` | multi-entity, multi-currency treasury: notice revisions, FX match failures, SSI changes, shared limits, debt repayment | operational baseline (Flash 100 / M3 61.39) |
| Source treasury 0.3.0 | `source-treasury-stress/quiet/hedged` | no internal cash or forecast given — risk ledger must be reconstructed from bank records, trade registry, CSA agreements and market factors | calibration candidate (stress avg Flash 66.43 / M3 100; risk items tightened in v1.1.0) |
| Equity event stream | `equity-event-001` | real SEC data: Alphabet Q1 2026 earnings night; SQL database + business-clock disclosure stream; pre-earnings forecast → post-release reconciliation → 10-Q verification | **v1.4.0: validity-first scoring refactor; 6 scored rollouts, mean 43.14 ± 5.61 (final config 4 runs: 42.01 ± 1.50)** |

## Flagship case: `equity-event-001`

An on-duty equity research analyst covers **Alphabet's Q1 2026 earnings night (2026-04-29, 15:00–21:30 ET)**:

1. **Before the release (deadline 15:55 ET):** build a nine-metric point forecast — total revenue, net revenue, TAC, Google Services revenue, Google Cloud revenue, Services operating income, Cloud operating income, consolidated operating income, and diluted EPS excluding one-offs — plus beat/miss probabilities, from the FY2025 10-K, historical XBRL facts, a frozen consensus snapshot and pre-release filings.
2. **After the 8-K release (deadline 16:20 ET):** reconcile the actuals, compute surprise vs consensus, classify beat/miss.
3. **After the 10-Q (deadline 21:20 ET):** verify the press-release figures against the 10-Q, bridge GAAP EPS to core EPS through the one-off equity-securities gain, and check segment margins.

The agent's workspace is a SQLite database containing filings, cleaned documents, 20k+ XBRL facts, daily prices, consensus estimates and issuer events. Every row carries `available_at_s`; the tool layer builds a filtered view for the current business time, so the future simply does not exist yet. Documents are served only after their real acceptance time, and reads/citations are audited.

Scoring (100 points, v1.4.0): nine-metric forecast composite **55** (including an accounting-identity consistency term), beat/miss probabilities 5 (bounded Brier Skill Score — 0.5/0.5 scores 0), one-off analysis 2, reconciliation 2 (validates the candidate's own consensus and recomputes surprise/beat), 10-Q verification 2 (nine reported values), timeliness 1, audit integrity 2 (per-submission timestamps), plus three LLM-rubric items (evidence chain 10, analysis logic 13, handover quality 8 — the last one grades the verification-stage summary). There is **no `must_pass` gate** and the single-case failure does not zero the whole task; `pass_threshold` is 0.85.

Calibration with `deepseek-flash` on LiteEval `90ed715` (six scored rollouts, identical model/harness/settings): **53.62 / 37.16 / 43.15 / 43.32 / 41.41 / 40.18** (mean 43.14, sd 5.61; final-configuration four: mean 42.01, sd 1.50). Applying the previous v1.3.1 weights to the same evidence gives mean 36.40 — the shift comes from weight reallocation toward analytical evidence (where the model does have measurable skill), not from loosening any criterion.

- Full design (database, prompts, tools, execution chain, rubric, judge prompts): [`docs/design/equity-event-stream-case-design.md`](docs/design/equity-event-stream-case-design.md) *(Chinese)*
- v1.4.0 scoring-refactor report (audit, per-file changes, scoring table, judge-variance and rollout comparison): [`docs/reports/equity-event-001-v3.3.1-report.md`](docs/reports/equity-event-001-v3.3.1-report.md) and [`docs/reports/equity-event-001-v3.3.1-audit.md`](docs/reports/equity-event-001-v3.3.1-audit.md)
- Earlier v1.3.1 rollout report with trajectories and per-check scores: [`docs/reports/equity-event-001-rollout-report.md`](docs/reports/equity-event-001-rollout-report.md) ([HTML](docs/reports/equity-event-001-rollout-report.html))
- Independent validation (realism / anti-lookahead / solvability): [`docs/validation/UNIFIED-ASSESSMENT.md`](docs/validation/UNIFIED-ASSESSMENT.md)

## Quickstart

Requirements: Python 3.11+, and **LiteEval ≥ `90ed715`** (the local-first agent evaluation backend; it supports resolving multiple workflow controllers in one benchmark run).

```bash
# 1. Install the evaluation platform
git clone https://github.com/SephirahVII/LiteEval.git
cd LiteEval && python -m pip install -e .

# 2. Initialize a local database and an owner (one-time; interactive)
liteeval owner-init --username owner
# Then create a project and a model connection (console or API); note PROJECT_ID / CONNECTION_ID.
# See LiteEval README and docs/connections-and-rollouts.md.

# 3. Register the workflow controllers and the JSON-action agent harness
cd /path/to/fin-stream-decision-bench
for wf in workflows/financial-stress workflows/treasury-network \
          workflows/source-treasury workflows/equity-event-stream; do
  liteeval harness "$wf" --project PROJECT_ID
done
liteeval harness harnesses/json_action --project PROJECT_ID

# 4. Validate, import and run the benchmark
liteeval benchmark validate .
liteeval benchmark import . --project PROJECT_ID
liteeval benchmark run RELEASE_ID --project PROJECT_ID \
  --agent-harness AGENT_REVISION \
  --workflow-harness WF_FINANCIAL_STRESS \
  --workflow-harness WF_TREASURY_NETWORK \
  --workflow-harness WF_SOURCE_TREASURY \
  --workflow-harness WF_EQUITY_EVENT \
  --target-connection CONNECTION_ID \
  --judge-connection CONNECTION_ID \
  --trusted-local
```

Notes:

- `--judge-connection` is required for cases that contain `llm_rubric` checks (`equity-event-001`, `source-treasury-*`); it may be the same model connection as the target.
- `--trusted-local` is required because tasks use the local `workspace` environment profile.
- Harness references are revisions returned by `liteeval harness`; if the same registry already holds a matching revision, register once and reuse the id.

Run the unit tests (no model calls, stdlib only):

```bash
python -m unittest discover -s tests -v
```

## Repository layout

```
dataset.toml                  benchmark manifest (tasks/*/task*.toml)
tasks/<case>/                 task.toml, prompt.md, environment/initial_workspace,
                              workflow-fixtures/, judge/ (ground truth + verifiers)
workflows/<family>/           harness.toml + controller.py (+ engine/data_service/ledger)
harnesses/json_action/        community JSON-action agent harness (conversation continuation,
                              reasoning passthrough, JSON/DSML action parsing)
tests/                        offline unit tests (judge edge cases, anti-leak scans)
docs/design/                  case designs (Chinese) — including the ILE-inspired flagship design
docs/calibration/             calibration protocols and analyses
docs/validation/              independent realism / anti-lookahead / solvability reviews
docs/reports/                 rollout reports (Markdown + HTML)
docs/proposals/               future task-family proposals
```

## Data, provenance and licenses

- **SEC EDGAR filings** (flagship): U.S. federal government works — public domain. Extracted with a descriptive User-Agent; every document preserves its real `acceptanceDatetime`; HTML→text conversion is deterministic (no LLM) and table numbers are byte-identical.
- **Yahoo Finance daily bars** (flagship): fetched from the public chart endpoint for research/benchmark use. Redistribution of Yahoo data may be subject to Yahoo's Terms of Service — if you intend commercial redistribution, replace them with a licensed market-data source.
- **Consensus snapshot** (flagship): 91.69B net revenue / 2.76 EPS for Q1 2026, quoted from the news document captured in *Investor's Last Exam* (O19 track; original source Zacks, as-of 2026-03-17). Cite ILE when reusing.
- **Per-case provenance**: `tasks/<case>/data/PROVENANCE.json` and `tasks/<case>/provenance/` record source URLs, SHA-256 hashes and the extraction scripts. These are also the audit trail for the anti-lookahead design.
- **Code and benchmark content**: licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)); third-party data remains subject to the upstream terms summarised in [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md). Simulation cases contain no third-party data.

## Limitations

- The benchmark measures decision quality on frozen business-clock replays, not real-time execution latency; a model's thinking time does not advance the business clock.
- Pretraining knowledge cannot be erased by access control. The flagship case mitigates this by (a) using issued-guidance era facts that were *not* in the tested model's memory (checked empirically) and (b) deterministic numeric tolerances; this remains a residual risk for other models.
- Runs use the trusted-local workspace profile; the evidence journal is a trust boundary, not a cryptographic proof. The verifier assumes the controller-produced evidence is untampered (see the audit-integrity check and the validation reports).
- LLM-rubric checks add sampling variance (≈ ±1.5 pp on the flagship total per re-judge) and occasional stochastic judge errors; the platform marks such runs `unscored` rather than scoring them. The rubrics carry 31/100 in the v1.4.0 flagship scoring, so repeat runs and `scoring_coverage` should be reported.

## Version history

- **v1.4.0** — validity-first scoring refactor for `equity-event-001`: rebalanced weights (55 forecast / 31 analysis-quality rubrics), bounded Brier Skill Score for probabilities, core-EPS probability event, per-submission audit, reconciliation self-consistency checks, 10-Q self-report removed from scoring, forecast accounting identity, new handover-quality rubric, `judge_timeout` 480 s, 23 offline tests; re-calibration on six rollouts (mean 43.14 ± 5.61) with v1.3.1 counterfactual comparison. See `docs/reports/equity-event-001-v3.3.1-report.md`.
- **Open-source release (v1.3.1)** — repository made public: Apache-2.0 license, third-party data/provenance notes, citation metadata, English README, unit-test CI; documentation sanitized of local absolute paths.
- **v1.3.1** — fixed the nine-metric forecast verifier (was averaging 7/9 metrics), re-ran three rollouts (38.61% / 29.13% / 33.01%, all ≤40%), updated the rollout report and design doc.
- **v1.3.0** — `equity-event-001` calibrated to the target band; forecast expanded to nine metrics and promoted to the dominant weight (74/100); added one-off bridge, peer-earnings noise (real MSFT/META/AMZN same-evening 8-K EX-99.1), hardened audit (basis/read/unpublished citations) and tighter LLM rubrics; hardened the JSON-action harness against protocol noise (JSON extraction + DSML parsing); added rollout report and unified validation assessment.
- **v1.2.0** — added `equity-event-001` (real SEC data, database time gating, deterministic + semantic judges) and `workflows/equity-event-stream`; fixed source-treasury risk-report freshness/metadata.
- **v1.1.0** — source-treasury document `as_of` metadata fix, risk-report freshness gate, stale import cleanup, dead design-doc links fixed.
- **v1.0.0** — initial import: LDI acceptance trio, treasury-network L8 baseline, source-treasury reconstruction trio.

## Citation

If you use this benchmark, please cite it via [`CITATION.cff`](CITATION.cff).

## Contributing

Issues and PRs are welcome — new task families, hardening of anti-lookahead audits, and additional calibration runs are especially useful. Please keep the design constraints: iterate at the package level (the platform stays unchanged unless the package format genuinely cannot express something), keep deterministic judging for numeric criteria, do not mix scores across versions, and provide provenance for any new data.
