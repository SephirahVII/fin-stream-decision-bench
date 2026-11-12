#!/bin/bash
# Reference solution (oracle): replays a complete, well-documented shift.
set -euo pipefail
cd /app

desk read googl-10k-20251231 >/dev/null
desk read googl-8k-20260402 >/dev/null

cat > /app/forecast.json <<'JSON'
{
  "payload": {
    "forecast": {
      "total_revenue_usd_m": 109896.0,
      "tac_usd_m": 15228.0,
      "net_revenue_usd_m": 94668.0,
      "google_services_revenue_usd_m": 89637.0,
      "google_cloud_revenue_usd_m": 20028.0,
      "google_services_operating_income_usd_m": 40589.0,
      "google_cloud_operating_income_usd_m": 6598.0,
      "operating_income_usd_m": 39696.0,
      "diluted_eps_ex_oneoffs_usd": 2.76
    },
    "probabilities": {"net_revenue_beat": 1.0, "eps_beat": 0.0},
    "basis": [
      {"source_doc_id": "googl-10k-20251231", "note": "FY2025 anchors from the 10-K: total revenues 402,836 USD m, TAC 59,926 USD m (14.9% of revenue), Google Cloud revenue 58,705 USD m; frozen consensus is 91,690 USD m net revenue and 2.76 core EPS. Forecast net revenue is built as 109,896 - 15,228 = 94,668 USD m; Cloud and Services operating income are anchored to the FY2025 segment margins."},
      {"source_doc_id": "googl-8k-20260402", "note": "The most recent 8-K confirms no material change to share count or capital structure, so the share count used for the core EPS estimate is unchanged."}
    ]
  },
  "summary": "Pre-release view with a rationale for all nine graded metrics, built only from the 10-K history, the frozen consensus and the 8-K filings available before the deadline. Total revenue 109,896 USD m, built as Google Services 89,637 + Google Cloud 20,028 + Other Bets 411 - hedging 180 = 109,896 USD m (the advertising/subscriptions split inside Services follows the FY2025 mix). TAC 15,228 USD m, 13.9% of revenue, consistent with the FY2025 TAC run-rate as Cloud mix grows. Net revenue 109,896 - 15,228 = 94,668 USD m, +3.25% versus the 91,690 USD m consensus. Google Services revenue 89,637 USD m implies +16.0% year over year on the FY2025 quarterly base; Cloud revenue 20,028 USD m implies +63% year over year on the Q1 2025 base of 12,260 USD m disclosed in the 10-K, an assumption about Cloud capacity and demand rather than a reported figure. Services operating income 40,589 USD m at a 45.28% margin and Cloud operating income 6,598 USD m at a 32.94% margin are assumptions anchored to the FY2025 segment margins. Consolidated operating income 39,696 USD m, a 36.1% consolidated margin. Core EPS 2.76 USD: GAAP EPS is not forecastable pre-release because an equity-securities one-off is unknown, so the forecast is core EPS excluding one-offs, assumed equal to consensus. Probabilities: net-revenue beat 1.0 (our +3.25% forecast is far outside the +/-0.5% in-line band, and the consensus gap is large relative to the +/-1,000-1,500 USD m estimation uncertainty); core-EPS beat 0.0 (2.76 equals the 2.76 consensus, the band is +/-0.5%, and the unknown one-off equity gain only adds noise, not a direction). Main estimation risk: Cloud revenue has the widest uncertainty, about +/-8% (+/-1,600 USD m), and a 100 bp change in the TAC rate would move net revenue by about 1,100 USD m, 1.2% of consensus; the Cloud risk is two-sided and the TAC risk is broadly neutral. These are explicit assumptions, not observed outcomes."
}
JSON
desk submit forecast /app/forecast.json >/dev/null

desk wait 3600 >/dev/null
desk wait 3695 >/dev/null
desk read googl-8k-20260429-ex991 >/dev/null

cat > /app/reconciliation.json <<'JSON'
{
  "payload": {
    "actuals": {
      "total_revenue_usd_m": 109896.0,
      "tac_usd_m": 15228.0,
      "net_revenue_usd_m": 94668.0,
      "diluted_eps_usd": 5.11
    },
    "consensus": {"net_revenue_usd_m": 91690.0, "diluted_eps_usd": 2.76},
    "surprise": {"net_revenue_pct_vs_consensus": 3.2479, "eps_pct_vs_consensus": 85.1449},
    "beat_miss": {"net_revenue": "beat", "eps": "beat"},
    "source_doc_ids": ["googl-8k-20260429-ex991"]
  },
  "summary": "The 8-K press release reports total revenues of 109,896 USD m and TAC of 15,228 USD m, so net revenue is 94,668 USD m, 3.2479% above the frozen 91,690 USD m consensus: a net-revenue beat. Diluted EPS is 5.11 USD, 85.14% above the 2.76 USD consensus; read through the one-off bridge, about 2.35 USD per share of the GAAP result is a non-recurring equity-securities gain (36,915 USD m pre-tax, 8,200 USD m tax), so the operational beat is much smaller than the GAAP figure suggests."
}
JSON
desk submit reconciliation /app/reconciliation.json >/dev/null

desk wait 21731 >/dev/null
desk read googl-10q-20260331 >/dev/null

cat > /app/verification.json <<'JSON'
{
  "payload": {
    "gaap": {
      "total_revenue_usd_m": 109896.0,
      "tac_usd_m": 15228.0,
      "net_revenue_usd_m": 94668.0,
      "operating_income_usd_m": 39696.0,
      "operating_margin_pct": 36.121424,
      "net_income_usd_m": 62578.0,
      "diluted_eps_usd": 5.11
    },
    "consistency": {"press_release_matches_10q": true},
    "one_off": {"equity_gain_usd_m": 36915.0, "core_eps_usd": 2.76},
    "segment_margins_pct": {"google_services": 45.281524, "google_cloud": 32.943879},
    "source_doc_ids": ["googl-8k-20260429-ex991", "googl-10q-20260331"]
  },
  "summary": "Forecast-to-actual review. Total revenue 109,896 vs forecast 109,896 (0.0% error); net revenue 94,668 vs 94,668; operating income 39,696 vs 39,696; core EPS 2.76 vs 2.76; Google Cloud revenue 20,028 vs 20,028; Google Services operating income 40,589 vs 40,589. The forecast was accurate by construction on the consolidated lines; the useful error is in the modelling habit, not the submitted numbers: the forecast assumed the 32.94% Cloud margin because the segment data supported it, but a reviewer relying on the FY2025 17.8% margin would have been badly wrong, so the next analyst should always re-base segment margins from the latest quarter rather than carrying the prior-year margin forward. Release-versus-10-Q reconciliation: total revenues 109,896 USD m appear in both the 8-K release and the 10-Q income statement; operating income 39,696 USD m appears in both; net income 62,578 USD m appears in both; diluted EPS 5.11 appears in both; cost of revenues 41,271 USD m in the 10-Q equals TAC 15,228 plus other cost of revenues 26,043 in the release, a presentation difference with no substantive inconsistency, and the 10-Q carries no segment operating income, so segment margins are sourced from the release segment table. GAAP-to-core EPS bridge: GAAP diluted EPS 5.11 = core EPS 2.76 + 2.35 per share. The 2.35 per share equals the after-tax equity-securities gain of about 28,715 USD m (36,915 USD m pre-tax less 8,200 USD m tax, 28,715 / 12,213 = 2.35) divided by 12,213 diluted shares; the same bridge shown in dollars is GAAP EPS 5.11 minus the one-off effect 2.35 equals core EPS 2.76, and the 22% effective tax rate on the gain is the main assumption in that bridge. Research lessons: (1) Cloud backlog above 460,000 USD m means Q2 Cloud revenue growth should be revised up from the FY2025 run-rate; (2) Cloud operating margin is now 32.94% versus 17.8% in FY2025, so 200-300 bp of further expansion is plausible and the segment-mix model should be re-based. Residual uncertainty for the next analyst: the largest remaining uncertainty is the TAC rate, where a 100 bp move is about 1,100 USD m (1.2% of consensus net revenue); given the Cloud-heavy mix shift, the more likely direction is a higher TAC ratio, which would reduce net revenue rather than increase it, so the next analyst should re-check the TAC rate first. The second uncertainty is the Cloud margin, where a 200 bp move is about 400 USD m of operating income; because the backlog implies continued Cloud scale, the more likely direction is further margin expansion, so the next analyst should treat the Cloud margin as likely to rise, not fall."
}
JSON
desk submit verification /app/verification.json >/dev/null

desk wait 23400 >/dev/null
desk status >/dev/null
