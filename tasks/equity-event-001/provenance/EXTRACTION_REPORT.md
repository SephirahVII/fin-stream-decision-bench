# Alphabet Q1 2026 real-data fixture — build & verification report

- Built at: `2026-11-10T20:18:08Z`
- Information shift (8-K acceptance): `2026-04-29T20:01:35Z`
- Task information cutoff: `2026-03-24T20:00:00Z` (2026-03-24 16:00 ET)
- Source of all numbers: SEC EDGAR (CIK 1652044) + Yahoo Finance + ILE O19 task JSON. No LLM was used to produce or alter any value.
- Raw bytes kept in `raw/`, derived fixtures in `data/`; every file listed in `manifest.json` with sha256 and size.

## 1. Required press-release figures (EX-99.1, `data/docs/000043_ex99_1.txt`)

| # | Required item | Regex used (multiline) | Matches | First match / result |
|---|---|---|---|---|
| 1 | consolidated revenues $109.9B | `revenues increased 22%, or 19% in constant currency, to \$109\.9 billion` | 1 | `revenues increased 22%, or 19% in constant currency, to $109.9 billion` |
| 2 | total revenues 109,896 (supplemental table) | `^Total revenues \| \$ \| 90,234 \| \$ \| 109,896$` | 2 | `Total revenues | $ | 90,234 | $ | 109,896` |
| 3 | TAC 15,228 | `^Total TAC \| \$ \| 13,748 \| \$ \| 15,228$` | 1 | `Total TAC | $ | 13,748 | $ | 15,228` |
| 4 | net revenue 94,668 | `(?<![\d,])94,668(?![\d,])` | 0 | **not found** |
| 5 | diluted EPS $5.11 (table row) | `^Diluted net income per share \| \$ \| 2\.81 \| \$ \| 5\.11$` | 1 | `Diluted net income per share | $ | 2.81 | $ | 5.11` |
| 6 | diluted EPS $5.11 (bullet) | `EPS increased 82% to \$5\.11` | 1 | `EPS increased 82% to $5.11` |
| 7 | net income 62,578 | `^Net income \| \$ \| 34,540 \| \$ \| 62,578$` | 3 | `Net income | $ | 34,540 | $ | 62,578` |
| 8 | Google Cloud 20,028 | `^Google Cloud \| 12,260 \| 20,028$` | 2 | `Google Cloud | 12,260 | 20,028` |
| 9 | operating income 39,696 | `^Operating income \| \$ \| 30,606 \| \$ \| 39,696$` | 1 | `Operating income | $ | 30,606 | $ | 39,696` |
| 10 | employees 194,668 | `^Number of employees \| 185,719 \| 194,668$` | 1 | `Number of employees | 185,719 | 194,668` |

### 1.1 `net revenue 94,668` — the one required figure the press release does not print

- With a non-digit boundary (`(?<![\d,])94,668(?![\d,])`) the press release contains **0** occurrences of 94,668. A naive substring search finds **1**, and the only hit is inside the employee count `194,668` (`Number of employees | 185,719 | 194,668`), so it is not a revenue figure.
- The phrase `net revenue` does not appear in EX-99.1 at all (case-insensitive count: 0).
- 94,668 is only reproducible arithmetically: `109,896 - 15,228 = 94,668` (USD millions) = 94.668 USD bn. The 10-Q contains no net-revenue line either; in the full 10-Q text the only `194,668` is the MD&A headcount row (`Number of employees`), which lies outside the extracted statement/note sections.
- This matches the O19 ground truth, where `q1_2026_rev_net_tac = 94.67` is attributed to a **news** document published `2026-06-19T13:00:05Z`, not to an issuer filing. Derived value stored in `data/o19_ground_truth.json` provenance note.

### 1.2 Corroboration in the 10-Q (`data/docs/000048_primary.txt`)

- Total revenues: 2 match(es) — `Total revenues | $ | 90,234 | $ | 109,896`
- TAC: 1 match(es) — `TAC | $ | 13,748 | $ | 15,228`
- Diluted EPS (label and values sit on separate source rows): 1 match(es) — `Diluted net income per share (Note 12) ⏎ $ | 2.81 | $ | 5.11`
- 10-K FY2023-25 Google Cloud revenue: 1 match(es) — `Google Cloud | 33,088 | 43,229 | 58,705`
- 10-K FY2023-25 total revenues: 1 match(es) — `Total revenues | $ | 307,394 | $ | 350,018 | $ | 402,836`

## 2. Acceptance timestamps

| accession | form | submissions `acceptanceDateTime` | index-headers `ACCEPTANCE-DATETIME` (ET→UTC) | equal | expected |
|---|---|---|---|---|---|
| 0001652044-26-000018 | 10-K | `2026-02-05T02:56:03Z` | `2026-02-05T02:56:03Z` (20260204215603) | yes | `2026-02-05T02:56:03Z` OK |
| 0001652044-26-000031 | 8-K | `2026-04-02T20:18:28Z` | `2026-04-02T20:18:28Z` (20260402161828) | yes | `2026-04-02T20:18:28Z` OK |
| 0001652044-26-000034 | 8-K | `2026-04-10T20:16:53Z` | `2026-04-10T20:16:53Z` (20260410161653) | yes | `2026-04-10T20:16:53Z` OK |
| 0001652044-26-000043 | 8-K | `2026-04-29T20:01:35Z` | `2026-04-29T20:01:35Z` (20260429160135) | yes | `2026-04-29T20:01:35Z` OK |
| 0001652044-26-000048 | 10-Q | `2026-04-30T01:02:11Z` | `2026-04-30T01:02:11Z` (20260429210211) | yes | `2026-04-30T01:02:11Z` OK |

- The ET→UTC conversion uses `zoneinfo.ZoneInfo("America/New_York")` (04-29/04-30 are EDT, 02-04 is EST), which is why the 10-Q lands on 2026-04-30 while its ET date is still 2026-04-29.
- `data/filings.csv` uses the ISO-Z value from `data.sec.gov/submissions` (exact to the second).

## 3. Prices (`data/prices.csv`, Yahoo Finance chart API)

| date | open | high | low | close | adjclose | volume | available_at_utc | is_future_after_2026-04-29T20:01:35Z |
|---|---|---|---|---|---|---|---|---|
| 2026-04-28 | 348.55 | 352.42 | 346.12 | 349.78 | 349.3466 | 27824100 | 2026-04-28T20:00:00Z | False |
| 2026-04-29 | 347.57 | 355.79 | 344.21 | 349.94 | 349.5065 | 35376300 | 2026-04-29T20:00:00Z | False |
| 2026-04-30 | 374.07 | 385.84 | 365.82 | 384.80 | 384.3232 | 72040000 | 2026-04-30T20:00:00Z | True |
| 2026-05-01 | 381.63 | 386.76 | 379.05 | 385.69 | 385.2122 | 30105200 | 2026-05-01T20:00:00Z | True |

- 2026-04-29 close: expected `349.94`, got `349.94` → **OK**
- 2026-04-30 close: expected `384.80`, got `384.80` → **OK**
- Close-to-close move on the first post-shift session: `384.80 / 349.94 - 1 = +9.96%`.
- 2026-04-29 16:00 ET = `2026-04-29T20:00:00Z`, i.e. 95 seconds *before* the 8-K acceptance at `20:01:35Z`, so that close is legitimately pre-shift (`is_future = False`); 2026-04-30 is the first future bar.
- Rows: 718 total (2024-01-02 .. 2026-11-10); 583 pre-shift rows in `data/returns_visible_pre_shift.csv` (simple close return and dividend-adjusted total return, first row blank).
- Yahoo returns floats (349.94000244140625, 384.79998779296875); OHLC/close are written at 2 decimals (US equity quote precision) and adjclose at 4 decimals. No null bars in the payload; `events` contains dividends only (no splits in window).

## 4. XBRL facts (`data/xbrl_facts.csv`, from companyfacts)

- Rows: 20777; distinct us-gaap concepts: 537; units: USD, USD/shares, pure, shares
- Period range: 2012-12-31 .. 2026-03-31; facts with period_end >= 2023-12-31: 4645; facts with period_end >= 2023-12-31 and <= 2026-03-31 (the case window): 4645.
- companyfacts holds 21399 us-gaap facts; 622 facts dated after 2026-03-31 (2026-06-04, 2026-06-05, 2026-06-30, 2026-07-31, 2026-09-30) were **excluded** so the fixture cannot leak post-event data. Every remaining row is a real reported fact, no synthetic values.
- The noise set is the full real us-gaap concept population (537 concepts, incl. quarterly, annual and instant balance-sheet facts back to 2012-12-31), far above the 200-concept requirement.

| concept | val | unit | fiscal | form | filed_utc |
|---|---|---|---|---|---|
| CostOfRevenue | 41271000000 | USD | 2026 Q1 | 10-Q | 2026-04-30T01:02:11Z |
| EarningsPerShareDiluted | 5.11 | USD/shares | 2026 Q1 | 10-Q | 2026-04-30T01:02:11Z |
| NetIncomeLoss | 62578000000 | USD | 2026 Q1 | 10-Q | 2026-04-30T01:02:11Z |
| OperatingIncomeLoss | 39696000000 | USD | 2026 Q1 | 10-Q | 2026-04-30T01:02:11Z |
| Revenues | 109896000000 | USD | 2026 Q1 | 10-Q | 2026-04-30T01:02:11Z |

### 4.1 Supplemental table vs XBRL

- `Revenues` Q1 2026 XBRL = 109,896,000,000 USD = 109,896 USD m → **matches** the 10-Q/press-release total revenues exactly (same accession 0001652044-26-000048).
- `CostOfRevenue` Q1 2026 XBRL = 41,271,000,000 USD = 41,271 USD m. That is **total cost of revenues** (`TAC 15,228 + other cost of revenues 26,043`), **not TAC**. companyfacts contains no TAC/traffic-acquisition concept at all, so the TAC figure exists only in filing text.
- Segment revenue (Google Cloud 20,028, Google Services 89,637) is **not** in companyfacts: the API exposes consolidated us-gaap facts only, with no segment/member dimension. Segment figures exist only in the 10-Q Note 15 / MD&A text, which is captured in `data/docs/000048_primary.txt` and `000018_primary.txt`.
- Net revenue 94,668 has no XBRL tag either (it is not a GAAP line), consistent with §1.1.
- Concept continuity caveat: `RevenueFromContractWithCustomerExcludingAssessedTax` has 87 USD facts but **none for 2026-03-31** (its last period is 2025-03-31, 90,234 USD m, 0001652044-25-000043); Alphabet's Q1 2026 revenue is tagged only under `Revenues`. A query that only reads the contract-revenue concept would return nothing for the event quarter.

## 5. Consensus & judge-side ground truth

- `data/consensus.csv`: 4 rows. The O19 task JSON contains exactly two estimate values — Q1 2026 revenue net of TAC `91.69` USD bn and Q1 2026 GAAP diluted EPS `2.76` USD, both `public_available_at = 2026-03-17T16:53:01Z` (Zacks article, news document `9c05375c-3fdd-43ea-941d-240072a010b2`). Two extra rows record the source-stated implications (20% YoY growth; 1.8% EPS decline) so they are not mistaken for independent estimates.
- No other estimate/metric fields exist in the task JSON; its remaining fields are `category_id, category_name, company, cutoff, evaluation_policy, ground_truth, id, judge_input_template, judge_kind, judge_response_schema, judge_system_prompt, judge_tools, max_score, question, rubrics, solver_system_prompt, solver_toolset_id, source_sha256, submission_mode, submission_schema, task_id, ticker, tools`.
- `data/o19_ground_truth.json`: all 6 ground-truth targets copied verbatim (value, unit, `public_available_at`, locator, excerpt, authority), flagged `judge_side_only: true`, with source task sha256.

## 6. Peers (metadata only, `data/peers.csv`)

- 25 rows across 8 issuers, EDGAR forms 8-K/10-Q/10-K/10-K/A accepted 2026-04-01..2026-05-05, from `data.sec.gov/submissions`.
- Same-evening cohort: MSFT 8-K 20:03:31Z / 10-Q 20:06:24Z, META 8-K 20:05:41Z / 10-Q 23:54:11Z, AMZN 8-K 20:18:55Z / 10-Q 22:48:09Z on 2026-04-29; AAPL 8-K 2026-04-30T20:30:41Z / 10-Q 2026-05-01T10:01:00Z.
- Columns include `title` = EDGAR `primaryDocDescription` (EDGAR exposes no human-readable filing title) and `filing_date`.

## 7. Files, sizes, failures

| file | bytes | contents |
|---|---|---|
| data/consensus.csv | 1311 | 4 rows |
| data/docs/000018_primary.txt | 17206 | 17186 chars clean text |
| data/docs/000031_primary.txt | 4697 | 4641 chars clean text |
| data/docs/000034_primary.txt | 8554 | 8450 chars clean text |
| data/docs/000043_ex99_1.txt | 23655 | 23561 chars clean text |
| data/docs/000043_primary.txt | 5289 | 5225 chars clean text |
| data/docs/000048_primary.txt | 22950 | 22857 chars clean text |
| data/filing_documents.csv | 1336 | 6 documents |
| data/filings.csv | 1713 | 5 filings |
| data/o19_ground_truth.json | 5775 | 6 targets |
| data/peers.csv | 5403 | 25 rows |
| data/prices.csv | 65311 | 718 daily bars |
| data/returns_visible_pre_shift.csv | 45472 | 583 returns |
| data/xbrl_facts.csv | 4116496 | 20777 rows, 537 concepts |

| raw/ | 9951216 | 28 files |
| data/ | 4325168 | 14 files |
| manifest.json | 14642 | all files |

Detailed per-file sizes (largest first):

| path | bytes | sha256 (12) |
|---|---|---|
| data/xbrl_facts.csv | 4116496 | `f1bbb2c7093a` |
| raw/companyfacts_CIK0001652044.json | 3250837 | `f87bc183f74b` |
| raw/0001652044-26-000018/goog-20251231.htm | 2616612 | `1ac2638bc971` |
| raw/0001652044-26-000048/goog-20260331.htm | 1714826 | `ba760ba0ba7a` |
| raw/0001652044-26-000043/googexhibit991q12026.htm | 311063 | `76fc1024b53d` |
| raw/submissions_CIK0001652044_001.json | 270779 | `5dd83de957e9` |
| raw/peers/CIK0000789019.json | 186258 | `8402c941d578` |
| raw/peers/CIK0000320193.json | 164858 | `88bb6d5b8501` |
| raw/peers/CIK0001318605.json | 162443 | `96b3689a2016` |
| raw/peers/CIK0001018724.json | 160075 | `427f2a8fd700` |
| raw/peers/CIK0001045810.json | 159914 | `db787ea65639` |
| raw/peers/CIK0000050863.json | 159346 | `d756db2711de` |
| raw/peers/CIK0001341439.json | 158530 | `5364c4ec08e6` |
| raw/peers/CIK0001326801.json | 157519 | `dde7d37241ec` |
| raw/submissions_CIK0001652044.json | 152278 | `679f595245e1` |
| raw/yahoo_GOOGL_daily.json | 79883 | `948fa5242eba` |
| data/prices.csv | 65311 | `731d1c103363` |
| raw/0001652044-26-000034/goog-20260407.htm | 54954 | `e9a01fe84e10` |

- `scripts/fetch_extra.py` (archive submissions, EX-99.1, 5 index-headers, 8 peer files, Yahoo): 16 artifacts, 0 errors (skipped because already present: 16).
- `scripts/dl.py` log: 12 fetches, 0 failures. Additional single fetches outside that log (submissions archive, EX-99.1 exhibit, 5 index-headers, 8 peer submissions) all returned HTTP 200; their bytes/sha256 are in `manifest.json`.
- Index-headers `PUBLIC DOCUMENT COUNT` (all documents incl. XBRL renderings): 000043=13, 000048=103, 000018=113, 000034=12, 000031=12. Only the primary document of each accession and the EX-99.1 press release were mirrored and cleaned; exhibit/certification/XBRL-rendering bytes were not downloaded.
- 000048/000018/000034/000031 exhibits were intentionally not downloaded (no press release attached); this is a scope choice, not a failure.

## 8. Fixture notes for the judge/DB

- `data/docs/*.txt` are deterministic HTML→text conversions (stdlib `HTMLParser`): hidden XBRL header blocks, `ix:header`, scripts and styles are dropped; table cells become ` | `-separated rows; numbers are byte-identical to the filing. Every section carries a `source: <filing_url>#<section>` line, and 10-Q/10-K files contain only the key sections (cover, statements, revenue/TAC notes, segment note, selected MD&A), while EX-99.1 is complete.
- `filings.csv.filing_url` points at the primary document; `filing_documents.csv` records both `raw_path` and `text_path`.
- Availability: all filing-derived rows use the filing's acceptance timestamp (the moment the bytes became public on EDGAR), not the 16:00 ET press-release embargo; the 8-K was accepted at 20:01:35Z, 95s after that day's close.
- Prices: `available_at_utc` is the 16:00 America/New_York close of each bar, DST-aware (EDT → 20:00Z, EST → 21:00Z).

## 9. Reproduce & validate

```
cd /tmp/ile_case_build
python3 scripts/dl.py            # SEC primaries + index.json + submissions + companyfacts (add --refresh to force)
python3 scripts/fetch_extra.py   # archive submissions, EX-99.1, index-headers, peers, Yahoo (add --refresh to force)
python3 scripts/build.py         # rebuilds data/, manifest.json and this REPORT.md
python3 scripts/validate.py      # independent re-hash + 287 fixture assertions
```

All scripts are stdlib-only (urllib, csv, json, hashlib, zoneinfo, html.parser) and were run with `3.12.16`.
`data/docs/*.txt` contains no LLM-authored text: the only added lines are the `source:`/`form:`/`note:` headers and `===== SECTION: ... =====` markers.
