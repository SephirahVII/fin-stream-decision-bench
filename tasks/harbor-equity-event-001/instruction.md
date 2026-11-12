You are the on-duty equity research analyst for a long-only fund. Today is
Wednesday 2026-04-29; your shift runs from 15:00 to 21:30 US/Eastern and the
subject is Alphabet Inc. (GOOGL), which reports Q1 2026 results after the close.

Your job is to produce a research view from the data that is public at each
point in time, and to deliver it in three graded submissions:

1. `forecast` before 15:55 ET: point estimates for nine Q1 2026 metrics, two
   beat probabilities and a short basis for each estimate.
2. `reconciliation` before 16:20 ET: the press release numbers, the frozen
   consensus you are measured against, your computed surprise and beat/miss
   calls, and a summary of what happened.
3. `verification` before 21:20 ET: the consolidated numbers re-checked against
   the Form 10-Q, the one-off earnings bridge, segment margins, and a handover
   summary for the next analyst.

All data access and submissions go through the `desk` tool. Start with
`desk manual`; it documents the tool costs, the three payload schemas, the
deadlines, the units, and the audit rules. Working notes:

- `desk status` shows the business clock, deadlines and action budget.
- `desk catalog`, `desk query "SELECT ..."` and `desk read <doc_id>` are the
  only ways to see market data and filings; nothing outside the desk is public.
- `desk wait <seconds>` advances the business clock; never guess a time.
- Write your payload JSON to a file and submit it, for example:
  `desk submit forecast /app/forecast.json` where the file holds
  `{"payload": {...}, "summary": "..."}`.
- The action budget is 120 desk actions; the evidence file is frozen by the
  desk automatically, so do not write anything into `/app/evidence`.

The task is a deterministic replay of a real earnings night: every timestamp,
filing and price comes from public records, and only information available at
the current business time is visible. Work carefully and leave an auditable
record of your reasoning in the summaries.
