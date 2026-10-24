"""Offline build, local patch inventory, wheel and reviewable source ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--skip-build",action="store_true",help="Repackage evidence around the already validated wheel")
args=parser.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
provenance=json.loads((root/"UPSTREAM_PROVENANCE.json").read_text(encoding="utf-8"))
changes=[]
for repo in provenance["repositories"]:
    dest=root/"vendor"/repo["package"]
    original=repo["source_files"]
    for relative,before in original.items():
        p=dest/relative
        after=sha(p) if p.exists() else None
        if after != before:changes.append(dict(package=repo["package"],file=relative,before=before,after=after))
    for p in sorted(dest.rglob("*")):
        rel=p.relative_to(dest).as_posix()
        if p.is_file() and rel not in original and not any(x in rel for x in ("__pycache__",".pytest_cache",".egg-info")):
            changes.append(dict(package=repo["package"],file=rel,before=None,after=sha(p)))
write(root/"LOCAL_CHANGES.json",dict(schema_version=1,changes=changes))
lic=root/"src/sixvolumes/data/licenses";lic.mkdir(exist_ok=True)
for repo in provenance["repositories"]:
    shutil.copyfile(root/repo["license_path"],lic/(repo["package"]+".LICENSE.txt"))
shutil.copyfile(root/"UPSTREAM_PROVENANCE.json",root/"src/sixvolumes/data/UPSTREAM_PROVENANCE.json")
shutil.copyfile(root/"LOCAL_CHANGES.json",root/"src/sixvolumes/data/LOCAL_CHANGES.json")
shutil.copyfile(root/"LOCAL_PATCHES.md",root/"src/sixvolumes/data/LOCAL_PATCHES.md")
shutil.copyfile(root/"CORE_RESOURCES.json",root/"src/sixvolumes/data/CORE_RESOURCES.json")
temp=root/"outputs/tmp/build";temp.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env.update(TEMP=str(temp),TMP=str(temp),PYTHONUTF8="1",PYTHONDONTWRITEBYTECODE="1")
env["PIP_NO_INDEX"]="1"
if not args.skip_build:
    result=subprocess.run([sys.executable,"-m","pip","wheel",".","--no-deps","--no-build-isolation","--disable-pip-version-check","--wheel-dir","wheelhouse"],cwd=root,env=env)
    if result.returncode:raise SystemExit(result.returncode)
elif not list((root/"wheelhouse").glob("sixvolumes_trust_pipeline-0.2.0-*.whl")):
    raise SystemExit("No existing core wheel to repackage")
ignore={"outputs","build","dist",".venv",".evaluation-deps",".build-tools",".pytest_cache","__pycache__",".git","pip-cache"}
files=[]
for p in sorted(root.rglob("*")):
    rel=p.relative_to(root)
    if p.is_file() and not any(part in ignore or part.endswith(".egg-info") for part in rel.parts) and p.name not in {"SOURCE_MANIFEST.json"}:
        files.append(p)
write(root/"SOURCE_MANIFEST.json",dict(schema_version=1,files=[dict(file=p.relative_to(root).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
release=root/"dist";release.mkdir(exist_ok=True)
target=release/"sixvolumes-0.2.0-offline-source.zip"
with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
    for p in files+[root/"SOURCE_MANIFEST.json"]:z.write(p,p.relative_to(root))
    # Only the intended synthetic demo and validation summaries; never temp data.
    for directory in (root/"outputs/demo-clean/report",root/"outputs/validation",root/"outputs/tokenizer-cache"):
        if directory.exists():
            for p in sorted(directory.rglob("*")):
                if p.is_file() and p.name != "archive-integrity.json" and (directory.name=="tokenizer-cache" or p.suffix in {".json",".jsonl",".html",".xml",".log",".md"}):z.write(p,p.relative_to(root))
write(release/"SHA256SUMS.json",dict(files=[dict(file=str(p.relative_to(root)),sha256=sha(p),bytes=p.stat().st_size) for p in [target]+sorted((root/"wheelhouse").glob("*.whl"))]))
print(target)
