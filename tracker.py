#!/usr/bin/env python3
"""
Renae Upload Tracker.

Uses public profile pages where possible. It deliberately records UNVERIFIED
when a platform blocks/withholds reliable timestamps rather than treating
that as zero uploads.

Usage:
  python tracker.py                 # rolling 24h check
  python tracker.py --date 2026-08-21  # historical target date (best effort)
"""
import argparse, json, re, sys, time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (compatible; RenaeUploadTracker/1.0)"

def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")

def parse_epoch_values(html):
    vals = []
    for x in re.findall(r'"(?:createTime|create_time|timestamp|datePublished|uploadDate)"\s*:\s*"?(\\d{9,13})', html):
        try:
            n=int(x); n=n/1000 if n>10**11 else n
            vals.append(datetime.fromtimestamp(n, timezone.utc))
        except Exception:
            pass
    return sorted(set(vals), reverse=True)

def check_account(a, target=None):
    now=datetime.now(timezone.utc)
    if target:
        start=datetime.fromisoformat(target).replace(tzinfo=timezone.utc)
        end=start+timedelta(days=1)
    else:
        end=now; start=now-timedelta(hours=24)
    try:
        html=fetch(a["url"])
        times=parse_epoch_values(html)
        hits=[t for t in times if start <= t < end]
        if not times:
            return {"status":"UNVERIFIED","count":None,"times":[]}
        return {"status":"PASS" if len(hits)>=3 else "BEHIND","count":len(hits),"times":[t.isoformat() for t in hits]}
    except Exception as e:
        return {"status":"UNVERIFIED","count":None,"times":[],"error":type(e).__name__}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date", help="UTC date YYYY-MM-DD for best-effort historical check")
    args=p.parse_args()
    with open("accounts.json","r",encoding="utf-8") as f: cfg=json.load(f)
    results=[]
    for a in cfg["accounts"]:
        r=check_account(a,args.date)
        results.append({**a,**r})
        print(f'{a["owner"]:8} {a["platform"]:9} @{a["username"]:25} {r["status"]:10} {r["count"] if r["count"] is not None else "-"}')
        time.sleep(.5)
    out={"checked_at":datetime.now(timezone.utc).isoformat(),"target_date":args.date,"results":results}
    os.makedirs("results",exist_ok=True)
    stamp=args.date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    with open(f"results/{stamp}.json","w",encoding="utf-8") as f: json.dump(out,f,indent=2)
    return 0

if __name__=="__main__":
    sys.exit(main())
