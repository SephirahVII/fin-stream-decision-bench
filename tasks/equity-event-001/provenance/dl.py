import json, os, sys, time, urllib.request, urllib.error, hashlib

UA = "Fin-Stream-Bench research wayne@example.com"
OUT = "/tmp/ile_case_build/raw"
LOG = []
count = {"n": 0}

def fetch(url, path, sleep=0.13):
    if os.path.exists(path) and os.path.getsize(path) > 0 and "--refresh" not in sys.argv:
        b = open(path, "rb").read()
        LOG.append({"url": url, "path": path, "status": "cached", "bytes": len(b)})
        return b
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Host": url.split("/")[2]})
            with urllib.request.urlopen(req, timeout=90) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip; b = gzip.decompress(b)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(b)
            count["n"] += 1
            time.sleep(sleep)
            LOG.append({"url": url, "path": path, "status": "ok", "http": 200, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
            return b
        except urllib.error.HTTPError as e:
            last = f"HTTPError {e.code} {e.reason}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    LOG.append({"url": url, "path": path, "status": "FAILED", "error": last})
    print("FAILED", url, last)
    return None

def main():
    os.makedirs(OUT, exist_ok=True)
    cik = "1652044"
    sub = fetch(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json", f"{OUT}/submissions_CIK{cik.zfill(10)}.json")
    facts = fetch(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json", f"{OUT}/companyfacts_CIK{cik.zfill(10)}.json")
    accs = ["0001652044-26-000043","0001652044-26-000048","0001652044-26-000018","0001652044-26-000034","0001652044-26-000031"]
    subj = json.loads(sub)
    rec = subj["filings"]["recent"]
    meta = {}
    for a in accs:
        i = rec["accessionNumber"].index(a)
        meta[a] = {k: rec[k][i] for k in ["accessionNumber","filingDate","reportDate","acceptanceDateTime","act","form","fileNumber","filmNumber","items","size","primaryDocument","primaryDocDescription","isXBRL","isInlineXBRL"]}
    json.dump(meta, open("/tmp/ile_case_build/scripts/sub_meta.json","w"), indent=1)
    for a in accs:
        nodash = a.replace("-","")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{nodash}"
        idx = fetch(f"{base}/index.json", f"{OUT}/{a}/index.json")
        j = json.loads(idx)
        items = j["directory"]["item"]
        names = [it["name"] for it in items]
        print(a, meta[a]["form"], meta[a]["acceptanceDateTime"], "files:", len(items))
        for it in items:
            print("   ", it["name"], it.get("size"), it.get("type"))
        # primary doc
        pd = meta[a]["primaryDocument"]
        fetch(f"{base}/{pd}", f"{OUT}/{a}/{pd}")
        # EX-99.x
        for it in items:
            nm = it["name"]
            if nm.lower().startswith("ex99") and not nm.endswith(".xml"):
                fetch(f"{base}/{nm}", f"{OUT}/{a}/{nm}")
    json.dump({"fetches": LOG, "count": count["n"]}, open(f"{OUT}/_fetch_log.json","w"), indent=1)

main()
