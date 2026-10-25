"""NegQuote v0.1.1 缺口修复复测：扩充"不+动词"否定线索（仅此一处改动）。

背景（v0.1 REPORT.md 第四节诚实发现第 2 条）：线索表未收录裸"不"字否定，
"支持→不支持"型最小编辑漏检 1/40。本脚本按该报告预告的方向做**最小修复**：
新增一组常用"不+动词"否定组合白名单（见 ADDITIONAL_CUES），其余一切不变：

- 探针语料：直接 `from run_negquote import E`（与 v0.1 同一冻结语料对象，零转录，
  并在运行时与 v0.1 结果 JSON 逐组核对 n 与 raw_levels 分布，确保语料/对齐未漂移）；
- 门控逻辑、裁决等级、适用范围：与 v0.1 逐字一致；
- 单"不"字与"不+名词/形容词"仍不收录（噪声大，留给 v1.0 的"不+动词"模式化扩充）。

预注册预期（写于运行前，跑完对照）：
- near_negation 39→40/40（唯一漏检"青禾…不支持"被"不支持"线索命中）；
- verbatim / paraphrase / fullwidth / control_neg 维持 0 触发（线索对称规则保护）；
- numeric_perturbation 2→3：新增触发为"绿源…合格→不合格"——该编辑本就是语义反转，
  触发在语义上正确，但按分组口径仍逐条披露为"非目标类触发"。

运行：`py -3.13 run_negquote_v011.py` → `negquote_results_v011.json`（v0.1 的
negquote_results.json 原样保留，不覆盖）。
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 导入 run_negquote 会同时完成 src 与 vendor/gewita/src 的 sys.path 注入，
# 并原样取得冻结探针语料 E（本脚本不复制、不修改语料）。
from run_negquote import E, CUES, GATED_LEVELS  # noqa: E402
from gewita.align import align_quote  # noqa: E402

#: v0.1.1 新增线索：常用"不+动词"否定组合白名单（冻结于运行前）。
#: 单"不"字噪声大（不同/不断/不错等），仍不收录；镜像方向（原文否定/引语肯定）
#: 与数字置换依旧是不覆盖类，见 REPORT.md 诚实边界。
ADDITIONAL_CUES = ["不支持", "不存在", "不包含", "不具备", "不符合", "不满足",
                   "不达标", "不同意", "不允许", "不接受", "不属于", "不合格",
                   "不通过", "不成立", "不适用", "不可行"]
CUES_V011 = sorted(set(CUES) | set(ADDITIONAL_CUES), key=len, reverse=True)
SUPPORTED = ("VERBATIM", "NEAR")


def first_cue(text: str) -> str | None:
    for cue in CUES_V011:
        if cue in text:
            return cue
    return None


def gate(quote: str, level: str, span_text: str | None) -> dict:
    if level not in GATED_LEVELS or span_text is None:
        return {"verdict": level, "gated": False, "cue": None, "span_text": span_text}
    cue = first_cue(quote)
    if cue and cue not in span_text:
        return {"verdict": "UNSUPPORTED_PENDING_REVIEW", "gated": True,
                "cue": cue, "span_text": span_text, "raw_level": level}
    return {"verdict": level, "gated": False, "cue": cue, "span_text": span_text}


def align_with_source(quote: str, source: str) -> dict:
    a = align_quote(quote, source)
    span_text = source[a.start:a.end] if a.start >= 0 else None
    r = gate(quote, a.level, span_text)
    r.update(raw_level=a.level, score=a.score)
    return r


_FW = str.maketrans("0123456789", "０１２３４５６７８９")


def fullwidth(s: str) -> str:
    return s.translate(_FW)


def main():
    groups = {"verbatim": [], "near_negation": [], "numeric_perturbation": [],
              "paraphrase": [], "fullwidth": [], "control_neg": []}
    for title, source, qv, qnear, qnum, qpara in E:
        groups["verbatim"].append({**align_with_source(qv, source), "title": title})
        if qnear:
            groups["near_negation"].append({**align_with_source(qnear, source), "title": title})
        if qnum:
            groups["numeric_perturbation"].append({**align_with_source(qnum, source), "title": title})
        if qpara:
            groups["paraphrase"].append({**align_with_source(qpara, source), "title": title})
        groups["fullwidth"].append({**align_with_source(fullwidth(qv), source), "title": title})
    for title, source, qv, _, _, _ in E[40:]:
        groups["control_neg"].append({**align_with_source(qv, source), "title": title})

    def stat(group):
        n = len(group)
        fired = sum(1 for r in group if r["gated"])
        levels = {}
        for r in group:
            levels[r["raw_level"]] = levels.get(r["raw_level"], 0) + 1
        return {"n": n, "gated": fired, "gate_rate": round(fired / n, 4) if n else None,
                "raw_levels": levels,
                "near_or_better_unmasked": sum(1 for r in group if r["raw_level"] in ("VERBATIM", "NEAR"))}

    summary = {k: stat(v) for k, v in groups.items()}
    misses = [r["title"] for r in groups["near_negation"] if not r["gated"]]
    false_fires = {k: [r["title"] for r in groups[k] if r["gated"]]
                   for k in ("verbatim", "paraphrase", "fullwidth", "control_neg")}

    # ---- 与 v0.1 冻结结果逐组核对：语料与对齐不允许漂移 ----
    v01_path = HERE / "negquote_results.json"
    diff_vs_v01, corpus_check = [], {"status": "v0.1 结果文件缺失，跳过核对"}
    if v01_path.exists():
        v01 = json.loads(v01_path.read_text(encoding="utf-8"))
        corpus_check = {"status": "passed", "note": "逐组 n 与 raw_levels 分布与 v0.1 完全一致"}
        for g, s01 in v01["summary"].items():
            s11 = summary[g]
            if s01["n"] != s11["n"] or s01["raw_levels"] != s11["raw_levels"]:
                corpus_check = {"status": "FAILED", "group": g}
                break
            if s01["gated"] != s11["gated"]:
                was_gated = {r["title"] for r in v01["details"][g] if r["gated"]}
                newly = [r["title"] for r in groups[g]
                         if r["gated"] and r["title"] not in was_gated]
                no_longer = [t for t in was_gated
                             if t not in {r["title"] for r in groups[g] if r["gated"]}]
                diff_vs_v01.append({"group": g, "gated_v01": s01["gated"],
                                    "gated_v011": s11["gated"],
                                    "newly_gated_titles": newly,
                                    "no_longer_gated_titles": no_longer})

    out = {"schema": "sixvolumes-preresearch-negquote/0.3",
           "protocol": "v0.1.1 缺口修复复测：仅新增'不+动词'线索白名单；探针语料 import 自 "
                       "run_negquote.E（未复制未改动），门控逻辑与 v0.1 逐字一致；"
                       "合成新语料；非第三方认证",
           "cues_v01": sorted(CUES, key=len, reverse=True),
           "cues_v011": CUES_V011,
           "additional_cues": ADDITIONAL_CUES,
           "corpus_check_vs_v01": corpus_check,
           "diff_vs_v01": diff_vs_v01,
           "summary": summary,
           "near_negation_misses": misses,
           "false_fires": {k: v for k, v in false_fires.items() if v},
           "details": groups}
    (HERE / "negquote_results_v011.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("corpus_check_vs_v01:", corpus_check)
    print("diff_vs_v01:", json.dumps(diff_vs_v01, ensure_ascii=False))
    print("near_negation_misses:", misses)
    print("false_fires:", {k: v for k, v in false_fires.items() if v})


if __name__ == "__main__":
    main()
