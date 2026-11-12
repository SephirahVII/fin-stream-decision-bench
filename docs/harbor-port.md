# Harbor port: equity-event-001

This branch publishes a [Harbor](https://github.com/harbor-framework/harbor) task
for the same case that ships as a LiteEval package in `tasks/equity-event-001`.
The LiteEval distribution on `main` is unchanged; this task only exists on
`harbor-port`.

## Why a second format

LiteEval runs benchmark packages through its own workflow-controller protocol:
the controller process drives a JSON action agent and freezes `evidence/*.json`
for offline scoring. Harbor runs container tasks with a shell-based agent, a
separate verifier image and a 0-1 reward. The underlying task logic, data,
deadlines, payload schemas and judge are shared, so the two formats can be
compared directly.

## Layout

```
tasks/harbor-equity-event-001/
  instruction.md            # agent-facing prompt (roles, deadlines, desk usage)
  task.toml                 # Harbor task config (schema_version 1.4)
  environment/
    Dockerfile              # agent image: desk daemon + CLI, non-root agent user
    files/
      desk/                 # engine.py, data_service.py, daemon.py, market.db,
                            # manual.md, scenario.json
      deskctl.py            # `desk` CLI installed into the image
      start-desk.sh         # entrypoint: starts the root daemon, then CMD
  solution/solve.sh         # oracle reference shift (10 desk actions)
  tests/
    Dockerfile              # verifier image (python:3.13-slim, copies /tests)
    test.sh                 # runs grade.py, writes /logs/verifier/reward.txt
    grade.py                # 7 deterministic checks + 3 LLM rubrics
    prompt.txt              # task prompt passed to the LLM judge
    judge/                  # verify_ingest.py, ground truth and rubrics
```

## How the environment works

The agent image starts `desk` (a root-owned daemon) before the agent runs. The
daemon owns the canonical SQLite database in `/opt/desk/market.db` (mode 600,
root) and the operation log in `/opt/desk/state` (mode 700). The agent user can
only reach data through the `desk` CLI over a Unix socket:

- `desk status`, `desk manual`, `desk catalog`
- `desk query "SELECT ..."` (read-only SQL over currently published tables)
- `desk read <doc_id>` (published filings only)
- `desk wait <seconds>` (advances the replayed business clock)
- `desk submit <phase> <payload.json>` (payload + summary, deadline-enforced)

The daemon replays the real 2026-04-29 earnings night: the business clock starts
at 15:00 ET, filings and market data only become visible at their real
publication times, and the three submissions are deadline-gated (`forecast` 15:55,
`reconciliation` 16:20, `verification` 21:20). Every action is recorded in a
journal, the action budget is 120, and the frozen evidence file is written by the
daemon; the agent user cannot edit the canonical state.

## Scoring

`tests/grade.py` mirrors the LiteEval package judge:

- seven deterministic checks (forecast composite, probabilities, one-off
  analysis, reconciliation, 10-Q verification, timeliness, audit integrity) -
  69 points - scored by `tests/judge/verify_ingest.py` against
  `tests/judge/ground_truth.json`;
- three binary-criterion LLM rubrics (evidence chain 10, analysis logic 13,
  handover quality 8) - 31 points - graded by `deepseek-flash` with the same
  judge contract as the platform (untrusted candidate, one verdict per
  criterion, weighted pass fraction).

The final reward is `points / 100` written to `/logs/verifier/reward.txt`; the
per-check detail is written to `/logs/verifier/detail.json`.

## Running

```bash
# from tasks/harbor-equity-event-001
harbor lint .
harbor run -p . -a oracle -y          # reference solution, expect reward near 1.0
harbor run -p . -a mini-swe-agent -m deepseek-flash \
  --base-url https://api.deepseek.com \
  --api-key-name DEEPSEEK_API_KEY \
  --api-format openai_chat_completions -y
```

`DEEPSEEK_API_KEY` must be exported in the host environment; Harbor forwards it
to the agent and verifier environments through `[agent]` / `[verifier.env]`
templating (`-y` confirms host env passthrough).

## Known limitations

- The verifier trust model is Harbor's: artifacts are collected from the agent
  container after the trial. The daemon writes them as root, but a root-capable
  agent could still tamper with `/app/evidence`; the canonical copy lives outside
  the agent's writable tree and can be compared in future hardening.
- The LLM rubric stage needs network access to `api.deepseek.com`. The reward
  therefore mixes deterministic scoring and a hosted model judge, exactly as in
  the LiteEval package; the two cannot be merged.
- Harbor tasks run through a shell agent loop (mini-swe-agent), while the LiteEval
  package uses a JSON-action protocol. Per-run variance between the two formats
  is expected; compare aggregate distributions, not single runs.

## Validation run (2026-11-12)

- Oracle reference solution: reward 0.92-0.93 (deterministic 69/69, LLM rubrics
  23-24/31).
- `mini-swe-agent` + `deepseek-flash` (DeepSeek-V4.1-Flash): reward 0.5295
  (deterministic 29.95/69, LLM rubrics 23/31) in 7m08s with 31 desk actions and
  all three submissions before their deadlines.
- LiteEval package on the same fixtures and model: 50.45 / 43.01 / 47.03
  (mean 46.83), five-model band 32.48-58.75 -> same band and same weak spot
  (forecast accuracy). See
  [docs/reports/equity-event-001-harbor-port.md](reports/equity-event-001-harbor-port.md).

## Package validation note

Validate the LiteEval package from a clean export, not from the live worktree:

```bash
git archive HEAD | tar -x -C /tmp/clean_export
liteeval benchmark validate /tmp/clean_export
```

The LiteEval directory loader walks the whole package root and rejects
non-regular or multiply-linked files. A live git worktree contains `.git`
objects with `nlink > 1`, so validating the working directory itself fails with
`Only regular, single-link files are supported`; that error is unrelated to the
Harbor task. The clean export of `main` (and of this branch) validates as
`valid: true, version: 1.4.1, task_count: 1`. On this branch the Harbor task
directory is not matched by the package `tasks.include` pattern, so the
LiteEval task count is unchanged.
