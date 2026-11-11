# Equity event desk — manual

## 1. Shift

You are the on-duty equity research analyst covering Alphabet Inc. (GOOGL). The shift runs from 15:00 ET to 21:30 ET on Wednesday 2026-04-29, through Alphabet's Q1 2026 earnings release. All tool outputs use business-clock seconds since 15:00 ET.

The desk database is `market.db` (SQLite) and this manual is `desk/manual.md`. Both are reachable through the desk tools below. The database holds issuer records, filing metadata, filing texts, XBRL facts, consensus estimates, peer filings and daily prices. Rows become visible only after their publication time; attempts to read records that are not published yet are rejected and count against the audit score.

## 2. Tools and costs (business seconds)

| action | cost | notes |
| --- | --- | --- |
| `catalog` | 5 | list the visible tables and columns |
| `query(sql)` | 15 | read-only SQL over published rows; at most 100 rows returned |
| `read(doc_id)` or `read(path)` | 10 | full text of a published filing document / this manual |
| `submit(phase, payload, summary)` | 10 | graded submission; schema below; rejected payloads still consume an action |
| `wait(until_s)` | 0 | advance to the next scheduled event or the given time, whichever is earlier |

Action budget for the shift: 120 actions.

## 3. Deadlines and graded deliverables

Three graded submissions. The latest submission for a phase before its deadline is the one graded.

| phase | deadline (business s) | deadline (ET) |
| --- | --- | --- |
| `forecast` | 3300 | 15:55 |
| `reconciliation` | 4800 | 16:20 |
| `verification` | 22800 | 21:20 |

The shift ends at 23400 (21:30 ET).

## 4. Reporting units and definitions

- Money: USD millions, one decimal is fine (`100000.0`). Percentages: percent (`30.00` means 30.00%). EPS: USD, two decimals.
- Total revenues: consolidated revenues for the quarter.
- Traffic acquisition costs (TAC): the TAC line reported in the release supplement.
- Net revenue: total revenues minus TAC.
- Segment revenues: Google Services and Google Cloud reported segment revenues.
- Segment operating income: segment operating income reported in the release segment table (Google Services and Google Cloud).
- Operating income: consolidated income from operations.
- Diluted EPS excluding one-offs: diluted GAAP EPS adjusted for the after-tax effect of one-off equity-securities gains/losses disclosed by the issuer. Where no such item exists, it equals GAAP diluted EPS.
- Surprise: `100 * (actual - consensus) / consensus` in percent, computed from the numbers you submit.
- beat: surprise greater than +0.5%; miss: surprise less than -0.5%; otherwise in-line.

Consensus benchmarks are frozen in the database; use the ones published for the quarter being reported. A consensus estimate fetched after the release is not usable.

## 5. Payload schemas

Every submission contains a top-level `summary` narrative (required for `reconciliation` and `verification`, optional for `forecast`).

### forecast

```json
{
  "forecast": {
    "total_revenue_usd_m": 100000.0,
    "net_revenue_usd_m": 85000.0,
    "tac_usd_m": 15000.0,
    "google_services_revenue_usd_m": 80000.0,
    "google_cloud_revenue_usd_m": 15000.0,
    "google_services_operating_income_usd_m": 25000.0,
    "google_cloud_operating_income_usd_m": 5000.0,
    "operating_income_usd_m": 30000.0,
    "diluted_eps_ex_oneoffs_usd": 3.00
  },
  "probabilities": {"net_revenue_beat": 0.5, "eps_beat": 0.5},
  "basis": [{"source_doc_id": "example-doc", "note": "what this document supports"}]
}
```

- `probabilities`: your probability that the reported net revenue (respectively GAAP diluted EPS) will come in above the frozen consensus. Values in [0,1].
- `basis`: 1–10 objects; each names a document id that you actually read and explains its role in the forecast.

### reconciliation

```json
{
  "actuals": {"total_revenue_usd_m": 100000.0, "tac_usd_m": 15000.0,
              "net_revenue_usd_m": 85000.0, "diluted_eps_usd": 3.00},
  "consensus": {"net_revenue_usd_m": 85000.0, "diluted_eps_usd": 3.00},
  "surprise": {"net_revenue_pct_vs_consensus": 0.0, "eps_pct_vs_consensus": 0.0},
  "beat_miss": {"net_revenue": "in-line", "eps": "in-line"},
  "source_doc_ids": ["example-doc"]
}
```

### verification

```json
{
  "gaap": {"total_revenue_usd_m": 100000.0, "tac_usd_m": 15000.0,
           "net_revenue_usd_m": 85000.0, "operating_income_usd_m": 30000.0,
           "operating_margin_pct": 30.0, "net_income_usd_m": 20000.0,
           "diluted_eps_usd": 3.00},
  "one_off": {"equity_gain_usd_m": 0.0, "core_eps_usd": 3.00},
  "consistency": {"press_release_matches_10q": true},
  "segment_margins_pct": {"google_services": 40.0, "google_cloud": 10.0},
  "source_doc_ids": ["example-doc"]
}
```

- `one_off.equity_gain_usd_m`: net gain/loss on equity securities in the quarter, as disclosed by the release (USD m; 0.0 if none).
- `one_off.core_eps_usd`: diluted EPS excluding the after-tax effect of that item.
- `consistency.press_release_matches_10q`: whether the consolidated figures in the release agree with the Form 10-Q.
- `segment_margins_pct`: segment operating margin from the segment operating income / segment revenue disclosed in the earnings release table.

## 6. Evidence and audit rules

- Every cited document id must be a real document that exists in the database, must have been published at or before the business time of the submission, and must have actually been read (`read`) before you cite it.
- Reading a document that is not published yet is rejected; the failed attempt is recorded and reduces the audit score.
- Rejected submissions also reduce the audit score.
- Only public documents may be cited. The forecast `basis` documents are audited the same way.
- Analysis in `summary` must be supported by what you actually observed; do not assert figures that you did not take from the database.

## 7. Scoring outline

- Forecast accuracy against the reported quarter (several reported metrics, each with its own tolerance).
- Probability calibration for the two beat events.
- Post-release reconciliation arithmetic and beat/miss calls.
- Post-10-Q verification of GAAP figures, the one-off adjustment and segment margins.
- Timeliness of the three submissions.
- Audit integrity (citations, reads, rejected actions).
- Evidence chain and analysis logic (qualitative review of your summaries).
