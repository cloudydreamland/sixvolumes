"""Local-first pipeline. A passed check means only its documented scope passed."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import platform
from urllib.parse import urlsplit

from . import __version__
from .lineage import redact_with_lineage, source_spans

STAGES = ("helan", "worddael", "gewita", "siftan", "tellan", "sothstan")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_json(path):
    return json.loads(Path(path).read_bytes().decode("utf-8-sig"))


def text_files(path: Path):
    path = path.resolve()
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    files = [p for p in files if p.suffix.lower() in {".txt", ".md"}]
    if not files:
        raise ValueError("Input must contain at least one UTF-8 .txt or .md document")
    base = path.parent if path.is_file() else path
    records = []
    for p in files:
        if not p.resolve().is_relative_to(base):
            raise ValueError("Document symlink escapes the input directory")
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        if not text.strip():
            raise ValueError(f"Empty input document: {p.name}")
        records.append((p.relative_to(base).as_posix(), text, digest(raw)))
    return records


def stage(name, status, summary, evidence=None, limitations=None):
    return dict(name=name, status=status, summary=summary, evidence=evidence or {}, limitations=limitations or [])


@dataclass
class Options:
    input: Path
    output: Path
    sources: Path | None = None
    quotes: Path | None = None
    contamination_index: Path | None = None
    ledger: Path | None = None
    sothstan_config: Path | None = None
    vault_dir: Path | None = None
    allow_live: bool = False
    require_all: bool = False
    max_chars: int = 300
    overlap_chars: int = 30
    dataset_kind: str = "user-supplied-unverified"
    pii_profile: str = "normalized"


def quote_checks(documents, options):
    from gewita import align_quote, parse_references
    refs = []
    for document_id, text, _ in documents:
        for ref in parse_references(text):
            refs.append(dict(document_id=document_id, index=ref.index, parsed=ref.parsed,
                             year=ref.year, entry_type=ref.entry_type,
                             existence="UNVERIFIED_OFFLINE"))
    sources = {key: (text, sha) for key, text, sha in (text_files(options.sources) if options.sources else documents)}
    checks = []
    if options.quotes:
        payload = load_json(options.quotes)
        if not isinstance(payload, dict) or not isinstance(payload.get("quotes"), list):
            raise ValueError("quotes JSON must contain a quotes array")
        seen = set()
        for item in payload["quotes"]:
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("id", "source", "quote")):
                raise ValueError("Each quote requires nonempty string id, source and quote")
            if item["id"] in seen:
                raise ValueError("Duplicate quote id")
            seen.add(item["id"])
            if item["source"] not in sources:
                checks.append(dict(id=item["id"], source=item["source"], level="SOURCE_UNAVAILABLE", verified=False))
                continue
            source, sha = sources[item["source"]]
            alignment = align_quote(item["quote"], source)
            evidence = source[alignment.start:alignment.end] if alignment.start >= 0 else ""
            safe_quote = redact_with_lineage(item["quote"])[0]
            safe_evidence = redact_with_lineage(evidence)[0]
            checks.append(dict(id=item["id"], source=item["source"], source_sha256=sha,
                               quote=safe_quote, evidence_text=safe_evidence,
                               **asdict(alignment), verified=alignment.level == "VERBATIM",
                               exact_literal=bool(evidence) and evidence == item["quote"]))
    status = "passed" if refs or checks else "unavailable"
    if any(not r["parsed"] for r in refs) or any(not c["verified"] for c in checks):
        status = "failed"
    return stage("gewita", status, f"格式解析 {sum(r['parsed'] for r in refs)}/{len(refs)}；引语逐字对齐 {sum(c['verified'] for c in checks)}/{len(checks)}",
                 dict(references=refs, quotes=checks, source_files=[dict(id=k, sha256=v[1]) for k, v in sources.items()],
                      quotes_file_sha256=digest(options.quotes.read_bytes()) if options.quotes else None),
                 ["离线格式解析和给定来源内的词面核对，不验证出版物真实存在、语义蕴含或事实真伪。",
                  "没有引语/参考文献输入时记录 unavailable，不以零检测项冒充通过。"])


def contamination_checks(documents, options):
    if not options.contamination_index:
        return stage("siftan", "unavailable", "未提供基准索引；未运行污染筛查", limitations=["缺少索引不等于未污染。"])
    from siftan import ContaminationIndex, screen
    index = ContaminationIndex.load(options.contamination_index)
    if not len(index):
        raise ValueError("Contamination index has no usable n-grams")
    cert = screen("knowledge-base", [(key, text) for key, text, _ in documents], index)
    payload = cert.to_dict()
    payload["index_file_sha256"] = digest(options.contamination_index.read_bytes())
    payload["records"] = [dict(id=r.record_id, exact_hits=r.hits, near_dup_ratio=r.near_dup_ratio) for r in cert.records]
    # Deliberately do not publish raw overlapping n-grams, which may contain PII.
    payload["input_stage"] = "original-before-redaction"
    return stage("siftan", "failed" if cert.flagged_count else "passed", f"{cert.label}：{cert.flagged_count}/{cert.total} 文档有索引字面重叠", payload,
                 [cert.honesty, "筛查在原文上进行，避免脱敏修改文本造成假阴性；报告不输出原始命中片段。"])


def ledger_checks(options):
    if not options.ledger:
        return stage("tellan", "unavailable", "未提供实际调用账本；未做用量对账", limitations=["本地文档处理没有产生真实模型 API 账单。"])
    from tellan import Ledger, reconcile_ledger
    if not options.ledger.is_file():
        raise ValueError("Ledger file does not exist")
    ledger = Ledger(options.ledger)
    ok, bad_seq = ledger.verify()
    if not ok:
        return stage("tellan", "failed", "账本哈希链校验失败", dict(chain_valid=False, bad_seq=bad_seq, file_sha256=digest(options.ledger.read_bytes())))
    records = ledger.records()
    if not records:
        return stage("tellan", "unavailable", "账本为空，无法评估调用用量")
    summary = reconcile_ledger(records, strategy="heuristic")
    counts = summary["status_counts"]
    status = "failed" if any(v for k, v in counts.items() if k.startswith("SUSPECT")) else "passed"
    if status == "passed" and counts.get("INSUFFICIENT_DATA", 0):
        status = "unavailable"
    summary.update(chain_valid=True, file_sha256=digest(options.ledger.read_bytes()), strategy="heuristic",
                   source_authenticity="user-supplied-unverified", price_status="historical-unverified-snapshot")
    return stage("tellan", status, f"{len(records)} 条调用记录；{counts}", summary,
                 ["哈希链只检测链不一致，不证明根记录真实，不抵挡整链重算或无外部锚定的尾部截断。",
                  "启发式用量区间不是厂商精确计数；价格是历史未核实快照，不能作为财务结算依据。",
                  "上传账本的真实性需要调用方提供原始请求和厂商对账单佐证。"])


def model_checks(options):
    if not options.sothstan_config:
        return stage("sothstan", "unavailable", "未配置真实模型端点与官方基线；未判定模型身份")
    config = load_json(options.sothstan_config)
    required = ("base_url", "model", "registry", "official_baseline_source")
    if not isinstance(config, dict) or not all(isinstance(config.get(k), str) and config[k] for k in required):
        raise ValueError("Sothstan config requires base_url/model/registry/official_baseline_source")
    url = urlsplit(config["base_url"])
    if url.scheme != "https" or url.username or url.password or url.query:
        raise ValueError("Real endpoint must be HTTPS without embedded credentials or query keys")
    registry_dir = (options.sothstan_config.parent / config["registry"]).resolve()
    from sothstan.baseline import load_registry
    registry = load_registry(registry_dir)
    baseline = registry.get(config["model"])
    rivals = [b for mid, b in registry.items() if mid != config["model"] and not b.is_demo]
    if baseline is None or baseline.is_demo or not rivals:
        return stage("sothstan", "unavailable", "需要目标及至少一个近邻模型的非 demo 官方基线")
    if not options.allow_live:
        return stage("sothstan", "unavailable", "配置已校验；未启用 --allow-live，不发送外部请求")
    import os
    from sothstan.runner import verify
    from sothstan.report import result_to_dict
    key_env = config.get("api_key_env")
    key = os.environ.get(key_env) if key_env else None
    if key_env and not key:
        return stage("sothstan", "unavailable", "配置指定的 API key 环境变量未设置")
    result = verify(base_url=config["base_url"], model=config["model"], baseline=baseline, rivals=rivals,
                    api_key=key, seed=int(config.get("seed", 20261023)),
                    max_requests=min(80, int(config.get("max_requests", 24))),
                    max_prompt_tokens=min(20000, int(config.get("max_prompt_tokens", 4000))),
                    timeout=min(30, float(config.get("timeout", 10))), retries=0)
    payload = result_to_dict(result, config["base_url"], config["model"], int(config.get("seed", 20261023)))
    payload["baseline_files"] = [dict(file=p.name, sha256=digest(p.read_bytes())) for p in sorted(registry_dir.glob("*.json"))]
    payload["official_baseline_source"] = config["official_baseline_source"]
    label = payload["verdict"]["label"]
    status = {"AUTHENTIC": "passed", "INCONCLUSIVE": "unavailable"}.get(label, "failed")
    return stage("sothstan", status, f"行为一致性结果：{label}", payload,
                 ["统计行为证据不是密码学身份认证。真实基线来源是调用方声明，需独立核实。",
                  "版本、采样和代理策略也会改变行为；转发攻击可能不可区分。"])


def run(options: Options):
    from worddael import RecursiveChunker
    input_path, output = options.input.resolve(), options.output.resolve()
    if not input_path.exists():
        raise ValueError("Input does not exist")
    if input_path.is_relative_to(output) or (input_path.is_dir() and output.is_relative_to(input_path)):
        raise ValueError("Input and output must not contain each other")
    if options.vault_dir:
        vault_dir = options.vault_dir.resolve()
        if vault_dir.is_relative_to(output) or output.is_relative_to(vault_dir):
            raise ValueError("Sensitive Vaults must be stored separately from the shareable report directory")
        vault_dir.mkdir(parents=True, exist_ok=True)
    if options.max_chars < 40 or not 0 <= options.overlap_chars < options.max_chars:
        raise ValueError("max_chars must be >=40 and 0 <= overlap_chars < max_chars")
    documents = text_files(input_path)
    if output.exists() and any(output.iterdir()):
        previous = output / "report.json"
        if not previous.is_file():
            raise ValueError("Output directory is not empty; choose a dedicated report directory")
        old = load_json(previous)
        if {d["id"] for d in old.get("documents", [])} != {d[0] for d in documents}:
            raise ValueError("Input file set changed; use a fresh output directory to avoid stale artifacts")
    output.mkdir(parents=True, exist_ok=True)
    chunker = RecursiveChunker(max_chars=options.max_chars, overlap_chars=options.overlap_chars)
    docs, chunks, entity_counts = [], [], Counter()
    for key, text, sha in documents:
        masked, vault, segments, entities = redact_with_lineage(text, options.pii_profile)
        entity_counts.update(e["type"] for e in entities)
        relative = Path("masked") / key
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(masked.encode("utf-8"))
        if options.vault_dir:
            dest = options.vault_dir / (key + ".vault.json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            vault.save(str(dest))
        docs.append(dict(id=key, input_sha256=sha, original_characters=len(text), masked_characters=len(masked),
                         masked_file=relative.as_posix(), masked_sha256=digest(masked.encode("utf-8")),
                         entities=entities, lineage=segments, vault_saved=bool(options.vault_dir),
                         roundtrip_verified=True))
        for c in chunker.chunk(masked):
            if c.text != masked[c.start:c.end]:
                raise ValueError("Chunk/source offset invariant failed")
            chunks.append(dict(id=f"{key}#{c.seq}", document_id=key, text=c.text, start=c.start, end=c.end,
                               sha256=digest(c.text.encode("utf-8")), masked_file_sha256=docs[-1]["masked_sha256"],
                               original_file_sha256=sha, source_spans=source_spans(c.start, c.end, segments)))
    stages = [stage("helan", "passed", f"处理 {len(docs)} 篇文档，替换 {sum(entity_counts.values())} 个规则识别实体",
                    dict(entity_counts=dict(entity_counts), roundtrip_verified=True, pii_profile=options.pii_profile,
                         normalization_validation="engineering regression after observed failures; independent new holdout still required"),
                    ["passed 表示转换/偏移/还原不变量通过，不代表敏感信息召回率为100%。",
                     "Vault 是含原始敏感值的明文映射，不是加密，也不是密钥；默认不落盘。",
                     "报告与切块仍可能含规则漏检信息，外发前按实际数据规则审查。"]),
              stage("worddael", "passed", f"生成 {len(chunks)} 个可追溯块；全部偏移恒等式通过",
                    dict(chunks=len(chunks), max_chars=options.max_chars, overlap_chars=options.overlap_chars,
                         coordinate_system="Python Unicode code points; offsets refer to masked document; source_spans map to original"),
                    ["切块结构验证不证明真实 RAG 回答质量或检索最优。"])]
    for name, check in (("gewita", lambda: quote_checks(documents, options)),
                        ("siftan", lambda: contamination_checks(documents, options)),
                        ("tellan", lambda: ledger_checks(options)),
                        ("sothstan", lambda: model_checks(options))):
        try:
            stages.append(check())
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            stages.append(stage(name, "error", f"输入或执行错误：{type(exc).__name__}",
                                dict(detail=str(exc))))
    statuses = Counter(s["status"] for s in stages)
    exit_code = 2 if statuses["error"] else 1 if statuses["failed"] else 3 if options.require_all and statuses["unavailable"] else 0
    overall = "error" if statuses["error"] else "failed" if statuses["failed"] else "partial" if statuses["unavailable"] else "passed"
    chunks_path = output / "chunks.jsonl"
    chunks_path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
    report = dict(schema_version="sixvolumes.evidence/v1", tool_version=__version__,
                  generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  runtime=dict(python=platform.python_version(), platform=platform.system(), core_optional_dependencies=False),
                  dataset_kind=options.dataset_kind, overall=overall, exit_code=exit_code,
                  scope="Chinese knowledge-base local transformations and explicitly configured evidence checks",
                  status_counts=dict(statuses), stages=stages, documents=docs,
                  chunks=dict(file="chunks.jsonl", count=len(chunks), sha256=digest(chunks_path.read_bytes())),
                  privacy=dict(raw_documents_exported=False, vault_encrypted=False, vault_saved=bool(options.vault_dir)),
                  notes=["partial 表示至少一卷没有证据，不等同六卷全部通过。",
                         "退出码0仅表示已执行且可判定的检查没有失败；--require-all 将缺证据映射到退出码3。",
                         "哈希用于复现与内容一致性，不是第三方认证、数字签名或真实性背书。"])
    stable = {k: v for k, v in report.items() if k not in {"generated_at", "runtime"}}
    report["evidence_sha256"] = digest(canonical(stable))
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    from .report import render_html
    (output / "report.html").write_text(render_html(report, chunks), encoding="utf-8")
    generated = [output / p for p in ("report.json", "report.html", "chunks.jsonl")]
    generated.extend(output / d["masked_file"] for d in docs)
    artifacts = [dict(file=p.relative_to(output).as_posix(), sha256=digest(p.read_bytes()), bytes=p.stat().st_size)
                 for p in sorted(generated)]
    (output / "artifacts.json").write_text(json.dumps(dict(schema_version=1, files=artifacts), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report
