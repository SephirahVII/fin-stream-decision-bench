#!/usr/bin/env python3
"""Fetch the raw artifacts not covered by dl.py (idempotent; --refresh to re-download)."""
import hashlib, json, os, sys, time, urllib.request
ROOT = "/tmp/ile_case_build"
RAW = os.path.join(ROOT, "raw")
UA = "Fin-Stream-Bench research wayne@example.com"
ACC = ["0001652044-26-000043", "0001652044-26-000048", "0001652044-26-000018",
       "0001652044-26-000034", "0001652044-26-000031"]
PEERS = ["789019", "1326801", "1018724", "320193", "1045810", "1318605", "1341439", "50863"]
ARCH = "https://www.sec.gov/Archives/edgar/data/1652044/"
JOBS = [
    ("https://data.sec.gov/submissions/CIK0001652044-submissions-001.json",
     "submissions_CIK0001652044_001.json", UA),
    ("https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm",
     "0001652044-26-000043/googexhibit991q12026.htm", UA),
    ("https://query2.finance.yahoo.com/v8/finance/chart/GOOGL?period1=1704067200&period2=1794321000&interval=1d&events=div,splits",
     "yahoo_GOOGL_daily.json", "Mozilla/5.0"),
]
for a in ACC:
    JOBS.append((ARCH + a.replace("-", "") + "/" + a + "-index-headers.html", a + "/" + a + "-index-headers.html", UA))
for cik in PEERS:
    JOBS.append(("https://data.sec.gov/submissions/CIK%s.json" % cik.zfill(10),
                 "peers/CIK%s.json" % cik.zfill(10), UA))

def main():
    refresh = "--refresh" in sys.argv
    log = []
    for url, rel, agent in JOBS:
        p = os.path.join(RAW, rel)
        if os.path.exists(p) and not refresh:
            log.append({"url": url, "path": p, "status": "skipped-exists",
                        "bytes": os.path.getsize(p), "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()})
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        err = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": agent})
                b = urllib.request.urlopen(req, timeout=90).read()
                open(p, "wb").write(b)
                err = None
                log.append({"url": url, "path": p, "status": "ok", "bytes": len(b),
                            "sha256": hashlib.sha256(b).hexdigest()})
                break
            except Exception as e:
                err = "%s: %s" % (type(e).__name__, e)
                time.sleep(1 + attempt)
        if err:
            log.append({"url": url, "path": p, "status": "error", "error": err})
        time.sleep(0.13)
    json.dump({"fetches": log, "refresh": refresh}, open(os.path.join(RAW, "_extra_fetch_log.json"), "w"), indent=1)
    bad = [e for e in log if e["status"] == "error"]
    print(json.dumps({"total": len(log), "errors": len(bad), "errors_detail": bad}, indent=1))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
