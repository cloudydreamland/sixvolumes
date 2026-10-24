import json
from pathlib import Path
import subprocess
import sys

import pytest

from sixvolumes.cli import demo, main, verify_artifacts
from sixvolumes.lineage import redact_with_lineage, source_spans
from sixvolumes.pipeline import Options, run


def make_input(tmp_path, text="这是知识库。联系电话13812345678。"):
    root = tmp_path / "input"
    root.mkdir()
    (root / "a.txt").write_text(text, encoding="utf-8")
    return root


def test_clean_demo_masks_and_preserves_lineage(tmp_path):
    report = demo(tmp_path / "demo")
    assert report["overall"] == "partial"
    states = {s["name"]:s["status"] for s in report["stages"]}
    assert list(states.values()) == ["passed"]*4 + ["unavailable"]*2
    output = tmp_path / "demo" / "report"
    chunks = [json.loads(line) for line in (output/"chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    masked = {d["id"]:(output/d["masked_file"]).read_bytes().decode("utf-8") for d in report["documents"]}
    assert chunks
    for c in chunks:
        assert masked[c["document_id"]][c["start"]:c["end"]] == c["text"]
        assert c["source_spans"]
    for filename in ["report.json", "report.html", "chunks.jsonl"]:
        data=(output/filename).read_text(encoding="utf-8")
        assert "13812345678" not in data
        assert "11010519491231002X" not in data
    assert not list(output.rglob("*.vault.json"))
    assert verify_artifacts(output) == 0


@pytest.mark.parametrize("scenario,stage", [("contaminated", "siftan"), ("bad-quote", "gewita")])
def test_negative_scenarios_fail_with_evidence(tmp_path, scenario, stage):
    report=demo(tmp_path/scenario, scenario)
    assert report["overall"] == "failed" and report["exit_code"] == 1
    assert next(s for s in report["stages"] if s["name"] == stage)["status"] == "failed"


def test_missing_evidence_is_not_passing(tmp_path):
    report=demo(tmp_path/"strict", require_all=True)
    assert report["exit_code"] == 3
    assert report["status_counts"]["unavailable"] == 2


def test_reproducible_demo_digest(tmp_path):
    a=demo(tmp_path/"one")
    b=demo(tmp_path/"two")
    assert a["evidence_sha256"] == b["evidence_sha256"]


def test_tampered_artifact_is_detected(tmp_path):
    demo(tmp_path/"demo")
    out=tmp_path/"demo"/"report"
    with (out/"chunks.jsonl").open("a",encoding="utf-8") as f:f.write('{"tampered":true}\n')
    assert verify_artifacts(out) == 1


def test_final_chunk_budget_includes_punctuation_and_overlap(tmp_path):
    text = "甲" * 256 + "，" + "乙" * 300 + "。"
    source = make_input(tmp_path, text)
    output = tmp_path / "report"
    report = run(Options(source, output, max_chars=256, overlap_chars=32))
    assert next(s for s in report["stages"] if s["name"] == "worddael")["status"] == "passed"
    chunks = [json.loads(line) for line in (output / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert chunks and max(len(c["text"]) for c in chunks) <= 256
    assert verify_artifacts(output) == 0


def test_lineage_handles_replacements_and_crlf():
    text="第一行\r\n联系电话13812345678，邮箱demo@example.com。"
    masked,vault,segments,entities=redact_with_lineage(text)
    assert vault.restore(masked) == text
    assert "\r\n" in masked
    assert entities and any(s["kind"]=="redaction" for s in segments)
    assert segments[0]["source_start"] == 0 and segments[-1]["source_end"] == len(text)
    for s in segments:
        if s["kind"]=="copy":
            assert masked[s["masked_start"]:s["masked_end"]] == text[s["source_start"]:s["source_end"]]
        else:
            spans=source_spans(s["masked_start"]+1, s["masked_end"]-1, segments)
            assert spans[0]["source_start"]==s["source_start"]
            assert spans[0]["source_end"]==s["source_end"]


def test_vault_separated_and_plaintext_explicit(tmp_path):
    source=make_input(tmp_path)
    opts=Options(source,tmp_path/"report",vault_dir=tmp_path/"private")
    report=run(opts)
    vault=json.loads((tmp_path/"private/a.txt.vault.json").read_text(encoding="utf-8"))
    assert "13812345678" in str(vault)
    assert report["privacy"]["vault_encrypted"] is False
    opts.vault_dir=opts.output/"vault"
    with pytest.raises(ValueError,match="separately"):
        run(opts)


def test_bad_index_produces_machine_error_report(tmp_path):
    source=make_input(tmp_path)
    bad=tmp_path/"bad.tsi";bad.write_bytes(b"invalid")
    report=run(Options(source,tmp_path/"report",contamination_index=bad))
    assert report["exit_code"]==2
    assert next(s for s in report["stages"] if s["name"]=="siftan")["status"]=="error"


def test_no_reference_is_unavailable_not_zero_of_zero_pass(tmp_path):
    source=make_input(tmp_path)
    report=run(Options(source,tmp_path/"out"))
    assert next(s for s in report["stages"] if s["name"]=="gewita")["status"]=="unavailable"


def test_empty_and_wrong_path_return_exit2(tmp_path):
    missing=tmp_path/"missing"
    assert main(["audit",str(missing),"-o",str(tmp_path/"out")])==2
    source=make_input(tmp_path, "  ")
    assert main(["audit",str(source),"-o",str(tmp_path/"out")])==2


def test_output_cannot_overwrite_input(tmp_path):
    source=make_input(tmp_path)
    with pytest.raises(ValueError,match="contain each other"):
        run(Options(source, source/"out"))


def test_html_escapes_untrusted_document_content(tmp_path):
    source=make_input(tmp_path,'<script>alert("x")</script>这是一段原文。')
    run(Options(source,tmp_path/"out"))
    html=(tmp_path/"out/report.html").read_text(encoding="utf-8")
    assert '<script>alert("x")</script>' not in html
    assert "&lt;script&gt;" in html


def test_broken_ledger_fails_without_fabricating_usage(tmp_path):
    from tellan import Ledger
    source=make_input(tmp_path)
    ledger=tmp_path/"api.jsonl"
    Ledger(ledger).append("chat_completion",model="demo",usage={"prompt_tokens":2,"completion_tokens":1})
    content=ledger.read_text(encoding="utf-8").replace('"prompt_tokens":2','"prompt_tokens":9').replace('"prompt_tokens": 2','"prompt_tokens": 9')
    ledger.write_text(content,encoding="utf-8")
    report=run(Options(source,tmp_path/"out",ledger=ledger))
    result=next(s for s in report["stages"] if s["name"]=="tellan")
    assert result["status"]=="failed" and result["evidence"]["chain_valid"] is False


def test_sothstan_demo_baselines_rejected_as_real_evidence(tmp_path):
    source=make_input(tmp_path)
    from sothstan.baseline import PACKAGE_REGISTRY
    config=tmp_path/"config.json"
    config.write_text(json.dumps(dict(base_url="https://example.com",model="aqua-70b",registry=str(PACKAGE_REGISTRY),official_baseline_source="synthetic-demo")),encoding="utf-8")
    report=run(Options(source,tmp_path/"out",sothstan_config=config))
    result=next(s for s in report["stages"] if s["name"]=="sothstan")
    assert result["status"]=="unavailable"


def test_cli_exit_code_for_negative_case(tmp_path):
    root=Path(__file__).resolve().parents[1]
    proc=subprocess.run([sys.executable,str(root/"run.py"),"demo","-o",str(tmp_path/"negative"),"--scenario","bad-quote"],capture_output=True)
    assert proc.returncode==1


def test_core_report_does_not_use_optional_tokenizer(monkeypatch):
    import worddael.eval.retrieval as retrieval
    from worddael.eval.report import full_report
    from types import SimpleNamespace
    a=full_report(profile="core")
    monkeypatch.setattr(retrieval,"_HAS_JIEBA",True)
    def forbidden(text):raise AssertionError("core must not invoke installed jieba")
    monkeypatch.setattr(retrieval,"jieba",SimpleNamespace(cut=forbidden),raising=False)
    assert full_report(profile="core")==a


@pytest.mark.parametrize("value", ["１３８１２３４５６７８", "138\u200b1234\u200b5678", "138 1234 5678", "１１０１０５１９４９１２３１００２Ｘ"])
def test_normalization_preserves_original_offset(value):
    from sixvolumes.pii import recognize_identifiers
    text="合成联系人电话/身份证："+value+"。"
    hits=recognize_identifiers(text)
    assert any(e.text==value for e in hits)
    for e in hits: assert text[e.start:e.end]==e.text
    masked,vault,_,_=redact_with_lineage(text)
    assert value not in masked
    assert vault.restore(masked)==text


@pytest.mark.parametrize("value", ["138\n12345678", "138  12345678", "138\r\n12345678"])
def test_normalization_does_not_join_fields_or_lines(value):
    from sixvolumes.pii import recognize_identifiers
    assert not any(e.type=="PHONE" for e in recognize_identifiers(value))
