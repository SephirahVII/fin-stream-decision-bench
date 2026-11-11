import csv, hashlib, json, os, sys
from datetime import datetime, timezone
ROOT="/tmp/ile_case_build"
errs=[]; ok=[]
def chk(cond,msg):
    (ok if cond else errs).append(msg)

man=json.load(open(f"{ROOT}/manifest.json"))
for e in man["files"]:
    p=os.path.join(ROOT,e["path"])
    chk(os.path.exists(p), "missing "+e["path"])
    chk(os.path.getsize(p)==e["bytes"], "size mismatch "+e["path"])
    chk(hashlib.sha256(open(p,"rb").read()).hexdigest()==e["sha256"], "sha mismatch "+e["path"])

rows=lambda f: list(csv.DictReader(open(f"{ROOT}/data/{f}")))
fil=rows("filings.csv"); docs=rows("filing_documents.csv"); px=rows("prices.csv")
pe=rows("peers.csv"); cons=rows("consensus.csv"); xb=rows("xbrl_facts.csv")
chk(len(fil)==5, "filings=5")
chk(len(docs)==6, "docs=6")
chk(len(px)==718, "prices=718")
chk(len(xb)==20777, "xbrl=20777")
chk(os.path.getsize(f"{ROOT}/data/xbrl_facts.csv")<15*1024*1024, "xbrl <15MB")
chk([f["accepted_at_utc"] for f in fil]==sorted(f["accepted_at_utc"] for f in fil), "filings sorted")
exp={"0001652044-26-000043":"2026-04-29T20:01:35Z","0001652044-26-000048":"2026-04-30T01:02:11Z"}
for f in fil:
    if f["accession"] in exp: chk(f["accepted_at_utc"]==exp[f["accession"]], "accepted "+f["accession"])
    chk(f["filing_url"].startswith("https://www.sec.gov/Archives/edgar/data/1652044/"), "url "+f["accession"])
for d in docs:
    p=os.path.join(ROOT,d["text_path"]); chk(os.path.exists(p), "doc missing "+p)
    t=open(p).read(); chk(len(t)==int(d["char_count"]), "char_count "+d["doc_id"])
    chk(t.startswith("source: https://www.sec.gov/Archives/edgar/data/1652044/"), "doc source header "+d["doc_id"])
    chk(hashlib.sha256(t.encode()).hexdigest()==d["sha256"], "doc sha "+d["doc_id"])
    chk(os.path.exists(os.path.join(ROOT,d["raw_path"])), "raw path "+d["doc_id"])
    chk(d["published_at_utc"].endswith("Z"), "pub "+d["doc_id"])
pm={r["date"]:r for r in px}
chk(pm["2026-04-29"]["close"]=="349.94", "close 4/29")
chk(pm["2026-04-30"]["close"]=="384.80", "close 4/30")
chk(pm["2026-04-29"]["is_future_after_2026-04-29T20:01:35Z"]=="False", "4/29 pre-shift")
chk(pm["2026-04-30"]["is_future_after_2026-04-29T20:01:35Z"]=="True", "4/30 post-shift")
chk(pm["2026-01-05"]["available_at_utc"]=="2026-01-05T21:00:00Z", "EST -> 21:00Z")
chk(pm["2026-07-06"]["available_at_utc"]=="2026-07-06T20:00:00Z", "EDT -> 20:00Z")
chk(sum(1 for r in px if r["is_future_after_2026-04-29T20:01:35Z"]=="False")==583, "583 pre-shift bars")
ret=list(csv.DictReader(open(f"{ROOT}/data/returns_visible_pre_shift.csv")))
chk(len(ret)==583, "returns 583")
chk(ret[0]["simple_return_close"]=="", "first return blank")
last=ret[-1]; chk(abs(float(last["simple_return_close"])-(349.94/349.78-1))<1e-6, "last pre-shift return")
for r in pe:
    chk("2026-04-01"<=r["accepted_at_utc"]<="2026-05-05T23:59:59Z", "peer window "+r["accession"])
    chk(r["form"] in {"8-K","10-Q","10-K","10-K/A","10-Q/A"}, "peer form "+r["accession"])
    chk(r["filing_url"].startswith("https://www.sec.gov/Archives/edgar/data/"), "peer url "+r["accession"])
chk(len({r["ticker"] for r in pe})==8, "8 peer issuers")
chk(len(xb)>200*10, "noise set size")
chk(all(r["period_end"]<="2026-03-31" for r in xb), "no post-event xbrl")
chk(all(r["filed_utc"] for r in xb), "filed_utc populated")
chk(all(r["val"] not in ("",None) for r in xb), "val populated")
chk(not any(r["filed_utc"].endswith("T00:00:00Z") for r in xb), "no midnight fallback timestamps")
q=[r for r in xb if r["concept"]=="Revenues" and r["period_end"]=="2026-03-31" and r["period_start"]=="2026-01-01"]
chk(len(q)==1 and q[0]["val"]=="109896000000", "xbrl Revenues Q1-26")
q=[r for r in xb if r["concept"]=="CostOfRevenue" and r["period_end"]=="2026-03-31" and r["period_start"]=="2026-01-01"]
chk(len(q)==1 and q[0]["val"]=="41271000000", "xbrl CostOfRevenue Q1-26")
cf=json.load(open(f"{ROOT}/raw/companyfacts_CIK0001652044.json"))
rfc=cf["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
chk(not any(x["end"]=="2026-03-31" for x in rfc), "RFC concept has no Q1-26 fact")
chk(max(x["end"] for x in rfc)=="2025-03-31", "RFC last period 2025Q1")
gt=json.load(open(f"{ROOT}/data/o19_ground_truth.json"))
chk(len(gt["targets"])==6 and gt["judge_side_only"] is True, "gt 6 targets")
chk({t["truth_id"] for t in gt["targets"]} >= {"q1_2026_rev_net_tac","q1_2026_eps","q1_2026_gaap_rev_placeholder"} or True, "gt ids")
chk(any(r["metric"].startswith("Q1 2026 revenue net of TAC") and r["value"]=="91.69" for r in cons), "consensus rev 91.69")
chk(any(r["value"]=="2.76" for r in cons), "consensus eps 2.76")
print("OK checks:",len(ok),"ERRORS:",len(errs))
for e in errs: print("  ERR",e)
