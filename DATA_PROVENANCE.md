# Data provenance and third-party terms

This benchmark is built on real public data where possible and on deterministic synthetic data
everywhere else. This file records what comes from where, how it was captured, and what the
licensing implications are. Per-case machine-readable provenance lives in
`tasks/<case>/data/PROVENANCE.json` (file hashes, source URLs) and `tasks/<case>/provenance/`
(capture/conversion scripts and extraction reports).

## 1. Equity event stream (`tasks/equity-event-001`, flagship)

Subject: Alphabet Inc. (GOOGL), fiscal quarter Q1 2026, decision shift 2026-04-29 15:00–21:30 ET.
Business-clock epoch: `2026-04-29T19:00:00Z`; business times are seconds since 15:00 ET.

| Artifact | Source | Capture method | Terms / notes |
| --- | --- | --- | --- |
| `filings.csv`, `filing_documents.csv`, `docs/*.txt` | SEC EDGAR (`https://www.sec.gov/Archives/edgar/data/1652044/...`, `data.sec.gov/submissions/CIK0001652044.json`) | Official Archives index + primary documents, fetched with a descriptive `User-Agent`; `filing_documents` preserves each filing's real `acceptanceDatetime` (e.g. the Q1 2026 earnings 8-K accepted `2026-04-29T20:01:35Z`) | U.S. federal government works; public domain (17 U.S.C. §105). HTML→text conversion is deterministic (no LLM); table rows are ` | `-separated and numbers are byte-identical to the filing |
| `xbrl_facts.csv` | SEC XBRL `companyfacts` API (`data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json`) | 537 us-gaap concepts, 20,777 facts, 2012-12-31 → 2026-03-31; facts whose `period_end` is after 2026-03-31 are excluded to avoid look-ahead in the raw extract | public domain; one fact per concept/period/filing |
| `prices.csv`, `returns_visible_pre_shift.csv` | Yahoo Finance public chart endpoint (`query2.finance.yahoo.com/v8/finance/chart/GOOGL`) | 718 daily bars 2024-01-02 → 2026-11-10; each bar's visibility time = 16:00 ET on its trade date (DST-aware); `returns_visible_pre_shift.csv` is derived | research/benchmark use; redistribution may be subject to Yahoo's Terms of Service — replace with a licensed market-data source for commercial redistribution |
| `consensus.csv` | Frozen analyst consensus as captured by **Investor's Last Exam** (ILE), task O19 "Consensus gaps and earnings surprises" (news document `9c05375c-3fdd-43ea-941d-240072a010b2`); original source Zacks, as-of `2026-03-17T16:53:01Z` | Quoted values: Q1 2026 revenue net of TAC `$91.69B`, GAAP diluted EPS `$2.76`; also source-stated +20% YoY revenue and −1.8% EPS implications | values are presented as a frozen snapshot for evaluation; cite ILE (see `CITATION.cff` and the ILE paper, arXiv:2610.38342) when reusing |
| `peers.csv`, peer 8-K EX-99.1 texts | SEC EDGAR (MSFT, META, AMZN same-evening earnings releases) | metadata for 8 issuers + three real press releases (available 17:03–17:19 ET) used as information-flow noise and optional read-through | public domain |
| `o19_ground_truth.json` (judge-side only) | ILE task O19 ground truth (realized values + provenance) | kept under `judge/provenance/`, never mounted into the agent workspace | used only for post-hoc scoring; cite ILE |

Look-ahead safety of the extraction:

- Every filing/document row carries its real acceptance time; the DB builder maps it to
  `available_at_s` relative to the business-clock epoch.
- Facts with `period_end > 2026-03-31` are dropped from the raw extract, and the DB still gates
  Q1 2026 facts behind the 10-Q acceptance time (`2026-04-30T01:02:11Z` → t = 21,731 s).
- Yahoo bars are gated at their trade-date close (16:00 ET), so the 2026-04-29 close becomes
  visible only after the forecast deadline.

## 2. Evaluation platform

The case runs on [LiteEval](https://github.com/SephirahVII/LiteEval) (`>= 90ed715`), a local-first
agent evaluation backend. The benchmark repository does not bundle platform code; the
`harnesses/json_action` agent harness is included here as benchmark content.

## 3. Licensing summary

- Benchmark content (task definitions, controllers, judges, docs, tests): Apache-2.0 — see
  [`LICENSE`](LICENSE).
- Third-party data listed above remains subject to the respective upstream terms. SEC EDGAR data is
  public domain. Yahoo Finance data and the Zacks/ILE consensus snapshot are included for
  research/benchmark use; replace them with licensed sources if you redistribute commercially.
- If you add data, update `tasks/equity-event-001/data/PROVENANCE.json` with URL + SHA-256 and a
  deterministic capture script under `tasks/equity-event-001/provenance/`.
