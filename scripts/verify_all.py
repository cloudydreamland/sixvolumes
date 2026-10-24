"""Run every component and integration suite, retaining logs and exact counts."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--profile",choices=("core","evaluation"),default="core")
parser.add_argument("--components", nargs="+", choices=("integration","helan","worddael","gewita","siftan","tellan","sothstan"))
parser.add_argument("--run-label", default="", help="Keep a focused rerun separate from the original full matrix")
args=parser.parse_args()
if args.run_label and not all(c.isalnum() or c in "-_" for c in args.run_label):
    raise SystemExit("run-label must be a single simple directory name")
if args.profile=="evaluation" and any(importlib.util.find_spec(p) is None for p in ("jieba","tiktoken")):
    raise SystemExit("evaluation requires requirements-evaluation.txt; missing extras are not silently ignored")
out=root/"outputs"/"validation"/args.run_label/args.profile
out.mkdir(parents=True,exist_ok=True)
temp=root/"outputs"/"tmp"/args.profile
temp.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
paths=[str(root/"src")]+[str(p/"src") for p in (root/"vendor").iterdir() if p.is_dir()]
if args.profile=="core":
    paths.insert(0,str(root/"scripts/core_env"))
    env["SIXVOLUMES_CORE_ONLY"]="1"
else:
    env.pop("SIXVOLUMES_CORE_ONLY",None)
env["PYTHONPATH"]=os.pathsep.join(paths+[env.get("PYTHONPATH","")])
env.update(PYTHONIOENCODING="utf-8",PYTHONUTF8="1",PYTHONDONTWRITEBYTECODE="1",TEMP=str(temp),TMP=str(temp))
results=[]
for name,cwd in [("integration",root)]+[(p,root/"vendor"/p) for p in ("helan","worddael","gewita","siftan","tellan","sothstan")]:
    if args.components and name not in args.components:continue
    command=[sys.executable,"-m","pytest","tests","-q","-o","addopts=","-p","no:cacheprovider", "--junitxml="+str(out/(name+".xml")),"--basetemp="+str(temp/name)]
    started=time.monotonic()
    proc=subprocess.run(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",timeout=300)
    log=out/(name+".log");log.write_text(proc.stdout,encoding="utf-8")
    totals=dict(tests=0,failures=0,errors=0,skipped=0)
    xml=out/(name+".xml")
    if xml.exists():
        for s in ET.parse(xml).getroot().iter("testsuite"):
            for k in totals:totals[k]+=int(s.get(k,0))
    totals["passed"]=totals["tests"]-totals["failures"]-totals["errors"]-totals["skipped"]
    results.append(dict(component=name,command=command,cwd=str(cwd),exit_code=proc.returncode,seconds=round(time.monotonic()-started,2),**totals,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
    print(name,proc.returncode,totals,flush=True)
summary=dict(profile=args.profile,run_label=args.run_label,components=args.components or "all",python=sys.version,results=results,all_passed=all(r["exit_code"]==0 for r in results),
             note="Core explicitly blocks optional imports. These are engineering tests, not independent real-world quality measurements.")
(out/"results.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
raise SystemExit(0 if summary["all_passed"] else 1)
