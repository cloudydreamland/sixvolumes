"""Install and verify the built core wheel without importing checkout code."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
wheel = next((root / "wheelhouse").glob("sixvolumes_trust_pipeline-0.2.0-*.whl"))
target = root / "outputs/installed-budget-wheel"
demo = root / "outputs/installed-budget-demo"
env = os.environ.copy()
temp = root / "outputs/tmp/install-smoke"
temp.mkdir(parents=True, exist_ok=True)
env.update(PIP_NO_INDEX="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8", TEMP=str(temp), TMP=str(temp))
command = [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--upgrade", "--target", str(target), str(wheel)]
proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")
assert proc.returncode == 0, proc.stdout + proc.stderr
code = '''
import importlib,json,sys
from pathlib import Path
target=Path(sys.argv[1]);sys.path.insert(0,str(target))
modules={}
for name in ("sixvolumes","helan","worddael","gewita","siftan","tellan","sothstan"):
    module=importlib.import_module(name);path=Path(module.__file__).resolve()
    assert path.is_relative_to(target.resolve()),path
    modules[name]=str(path)
from worddael import RecursiveChunker
text="甲"*256+"，"+"乙"*300+"。"
chunks=RecursiveChunker(max_chars=256,overlap_chars=32).chunk(text)
assert max(len(c.text) for c in chunks)<=256
from sixvolumes.cli import demo,verify_artifacts
out=Path(sys.argv[2]);report=demo(out)
assert report["overall"]=="partial" and verify_artifacts(out/"report")==0
licenses=list((target/"sixvolumes/data/licenses").glob("*.LICENSE.txt"))
assert len(licenses)==6
assert (target/"sixvolumes/data/CORE_RESOURCES.json").exists()
print(json.dumps(dict(imports=modules,budget_max=max(len(c.text) for c in chunks),demo=report["overall"],artifacts_verified=True,retained_core_licenses=len(licenses))))
'''
smoke = [sys.executable, "-I", "-c", code, str(target), str(demo)]
tested = subprocess.run(smoke, cwd=root / "outputs", env=env, capture_output=True, text=True, encoding="utf-8")
assert tested.returncode == 0, tested.stdout + tested.stderr
result = dict(wheel=wheel.relative_to(root).as_posix(), wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
              install_command=command, isolated_python=True, exit_code=tested.returncode, smoke=json.loads(tested.stdout.splitlines()[-1]))
path = root / "outputs/validation/budget-fix/installed-wheel.json"
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(dict(exit_code=0,wheel_sha256=result["wheel_sha256"],budget_max=result["smoke"]["budget_max"])))
