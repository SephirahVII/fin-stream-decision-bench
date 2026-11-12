# Harbor port of equity-event-001: first model trial

**Date:** 2026-11-12
**Branch:** `harbor-port`
**Task:** `tasks/harbor-equity-event-001/`
**Harbor:** 0.25.0
**Agent:** `mini-swe-agent` (shell loop)
**Model:** `deepseek-flash` (DeepSeek-V4.1-Flash), OpenAI-compatible endpoint `https://api.deepseek.com`
**Judge model:** `deepseek-flash` (same endpoint, separate verifier container)

## 1. What was run

This branch ports the LiteEval package `tasks/equity-event-001` to Harbor:
the same real SEC fixtures, the same business clock and the same 100-point
scoring split (69 deterministic + 31 LLM rubric) wrapped in a Harbor task with
an agent container and a separate verifier container.

```bash
# from tasks/harbor-equity-event-001
harbor run -p . -a oracle -y -o /tmp/harbor_jobs --job-name oracle4
harbor run -p . -a mini-swe-agent -m openai/deepseek-flash \
  --base-url https://api.deepseek.com \
  --api-key-name DEEPSEEK_API_KEY \
  --api-format openai_chat_completions -y \
  -o /tmp/harbor_jobs --job-name miniswe2
```

`DEEPSEEK_API_KEY` was exported in the host environment. The agent phase ran
inside the task image (`python:3.13-slim` with the desk daemon on a Unix socket,
non-root `agent` user, DB mode 600 owned by root), and the verifier ran in a
separate image built from `tests/Dockerfile`.

## 2. Results

| run | score (0-1) | deterministic (69) | LLM rubrics (31) | wall time |
|---|---|---|---|---|
| Oracle reference solution | 0.920 (repeat runs 0.92-0.93) | 69.00 | 23.0-24.0 | ~2m20s |
| **mini-swe-agent + deepseek-flash** | **0.5295** | **29.95** | **23.00** | 7m08s |

Trial metadata: 1 trial, 0 exceptions, `verifier_environment_mode=separate`,
agent phase 20:56:01-20:59:54Z, verifier phase 20:59:54-21:02:08Z,
usage 1,966,362 input tokens (1,900,928 cached) and 41,145 output tokens.

### Per-check breakdown (model run)

| check | weight | score | points | note |
|---|---|---|---|---|
| forecast_composite | 55 | 0.3256 | 17.91 | nine pre-release metrics; Cloud/segment line misses |
| probabilities | 5 | 0.6144 | 3.07 | Brier skill score against two binary events |
| one_off_analysis | 2 | 1.0 | 2.00 | one-off bridge found after the release |
| reconciliation_actuals | 2 | 0.999 | 2.00 | press-release actuals and consensus |
| tenq_verification | 2 | 0.985 | 1.97 | 10-Q cross-check |
| timeliness | 1 | 1.0 | 1.00 | all three submissions before deadline |
| audit_integrity | 2 | 1.0 | 2.00 | no unpublished/unknown citations |
| evidence_chain | 10 | 1.0 | 10.00 | claims traced to cited filings |
| analysis_logic | 13 | 0.3846 | 5.00 | L1/L2/L5 fail on the model's rationale text |
| handover_quality | 8 | 1.0 | 8.00 | forecast-vs-actual and GAAP-to-core handover |

### What the model actually did

The shell agent made 31 desk actions in the 120-action budget and submitted all
three phases on time:

- read the FY2025 10-K, the 2026-04-02 and 2026-04-10 8-Ks;
- forecast at t=325s (payload: total 107,400 / TAC 15,100 / net 92,300 USD m,
  Services 89,000, Cloud 17,800, core EPS 2.79, probabilities 0.7/0.55),
  with per-metric basis notes anchored to FY2025 revenue, TAC ratio, segment
  margins and the frozen consensus;
- waited for and read the 8-K press release, then submitted reconciliation at
  t=3,715s (actuals 109,896/15,228/94,668/5.11, consensus 91,690/2.76,
  surprise 3.2474%/85.1449%, beat/beat);
- waited for and read the 10-Q, then submitted verification at t=21,751s
  (GAAP lines, one-off bridge 36,915 pre-tax / ~2.35 per share / core EPS 2.76,
  segment margins, release-vs-10-Q consistency, handover summary).

The forecast was the differentiator: total revenue was 2.27% low, Cloud revenue
11.1% low and segment operating income far off, which is exactly the capability
the LiteEval runs showed as the model's weak spot.

## 3. Consistency with the LiteEval package

The LiteEval distribution (v1.4.0, same fixtures, same judge, DeepSeek-V4.1-Flash)
scored 50.45 / 43.01 / 47.03 (mean 46.83, sd 3.72) across three runs. The Harbor
trial scored 52.95, about +6 points above that mean and inside the LiteEval
single-run spread. Across five models the LiteEval band is 32.48-58.75, so the
Harbor trial sits inside the same band.

The check profile also matches: deterministic extraction, reconciliation,
timeliness, audit and evidence are near-saturated, and forecast accuracy plus
the analysis rubric carry the score. The differences that remain are expected
from the format change:

- Harbor uses a shell agent (`mini-swe-agent`) instead of the JSON-action
  protocol, so exploration and payload construction are freer;
- one Harbor trial vs three LiteEval runs per model (single-run variance);
- the harbor verifier calls the same judge contract but is a separate service,
  and the run used a single model instance.

Conclusion: **the Harbor port runs end-to-end and produces a score consistent
with the LiteEval package** (same band, same weak spot), which was the goal of
this port.

## 4. Reproducing and limitations

- `harbor lint .` passes; the oracle solution scores 0.92-0.93 (deterministic
  69/69; the remaining gap is LLM-rubric sampling on the reference summaries).
- The agent container blocks direct DB reads: the database is mode 600 owned by
  root and the agent talks to a root daemon over `/run/desk/desk.sock`; the
  separate verifier receives evidence through Harbor artifacts materialized at
  their original paths.
- Residual limits: the LLM-rubric stage needs network access to
  `api.deepseek.com`; the verifier trust model is Harbor's artifact trust model;
  Harbor and LiteEval scores should not be mixed in one average.
- Trial artifacts (kept out of the repository): `/tmp/harbor_jobs/miniswe2/`,
  oracle reference `/tmp/harbor_jobs/oracle4/`.
