from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys

from . import __version__
from .pipeline import Options, canonical, digest, run, load_json


def demo(destination, scenario="clean", require_all=False):
    from importlib.resources import files
    from siftan.index import build_index
    root = Path(destination).resolve()
    sample = Path(str(files("sixvolumes").joinpath("data/demo")))
    inputs = root / "inputs" / scenario
    shutil.copytree(sample, inputs, dirs_exist_ok=True)
    index_path = root / "synthetic-benchmark.tsi"
    baseline = (inputs / "benchmark.txt").read_text(encoding="utf-8")
    build_index([baseline], name="SYNTHETIC-DEMO-ONLY", sources=["bundled original synthetic benchmark"],
                created_at="2026-10-23", builder="sixvolumes-demo").save(index_path)
    # Gzip headers otherwise embed write time / filename and change the artifact
    # digest even though the index body and all inputs are identical.
    import gzip
    index_path.write_bytes(gzip.compress(gzip.decompress(index_path.read_bytes()), mtime=0))
    if scenario == "contaminated":
        (inputs / "knowledge" / "injected-benchmark.txt").write_text(baseline, encoding="utf-8")
    if scenario == "bad-quote":
        payload = load_json(inputs / "quotes.json")
        payload["quotes"][0]["quote"] = "木星上的棉花每天自动完成财务审计。"
        (inputs / "quotes.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return run(Options(input=inputs / "knowledge", output=root / "report", sources=inputs / "sources",
                       quotes=inputs / "quotes.json", contamination_index=index_path,
                       dataset_kind="synthetic-original-demo; not a real customer or production benchmark",
                       require_all=require_all, max_chars=180, overlap_chars=20))


def verify_artifacts(directory):
    root = Path(directory).resolve()
    manifest = load_json(root / "artifacts.json")
    errors = []
    for item in manifest["files"]:
        path = (root / item["file"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
            errors.append(item["file"])
    report = load_json(root / "report.json")
    stable = {k:v for k,v in report.items() if k not in {"generated_at", "runtime", "evidence_sha256"}}
    if digest(canonical(stable)) != report["evidence_sha256"]:
        errors.append("report.evidence_sha256")
    print(json.dumps(dict(status="failed" if errors else "passed", changed_files=errors,
                          limitation="Content consistency only; no signature or external trust anchor"), ensure_ascii=False))
    return 1 if errors else 0


def parser():
    p=argparse.ArgumentParser(prog="sixvolumes", description="六卷书中文知识库证据管线；核心零必需第三方依赖")
    p.add_argument("--version", action="version", version=__version__)
    sub=p.add_subparsers(dest="command", required=True)
    audit=sub.add_parser("audit", help="处理 UTF-8 txt/md 知识库并输出 JSON+HTML")
    audit.add_argument("input", type=Path)
    audit.add_argument("-o", "--output", type=Path, required=True)
    for field in ("sources", "quotes", "contamination-index", "ledger", "sothstan-config", "vault-dir"):
        audit.add_argument("--"+field, type=Path)
    audit.add_argument("--max-chars", type=int, default=300)
    audit.add_argument("--overlap-chars", type=int, default=30)
    audit.add_argument("--allow-live", action="store_true", help="显式允许模型审计外部请求；仅此项可能产生API费用")
    audit.add_argument("--require-all", action="store_true", help="任一卷 unavailable 返回退出码3")
    audit.add_argument("--dataset-kind", default="user-supplied-unverified")
    audit.add_argument("--pii-profile", choices=("native","normalized"), default="normalized")
    d=sub.add_parser("demo", help="创建明确标注为合成的演示输入并运行")
    d.add_argument("-o", "--output", type=Path, default=Path("outputs/demo"))
    d.add_argument("--scenario", choices=("clean", "contaminated", "bad-quote"), default="clean")
    d.add_argument("--require-all", action="store_true")
    v=sub.add_parser("verify", help="复核报告工件哈希，不认证来源真实性")
    v.add_argument("directory", type=Path)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command == "verify":
            return verify_artifacts(args.directory)
        if args.command == "demo":
            report=demo(args.output, args.scenario, args.require_all)
            output=args.output / "report"
        else:
            options=Options(**{k:v for k,v in vars(args).items() if k != "command"})
            report=run(options)
            output=args.output
        print(json.dumps(dict(overall=report["overall"], exit_code=report["exit_code"],
                              statuses={s["name"]:s["status"] for s in report["stages"]},
                              report=str((output / "report.html").resolve()), evidence_sha256=report["evidence_sha256"]),
                         ensure_ascii=False, indent=2))
        return report["exit_code"]
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"sixvolumes: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
