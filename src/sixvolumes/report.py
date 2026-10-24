"""Standalone, escaped HTML; no external scripts, fonts, or network requests."""
from html import escape
import json

LABELS = {"passed": "已执行 · 通过", "failed": "发现问题", "unavailable": "证据未提供", "error": "执行错误", "partial": "部分完成"}
VOLUMES = {"helan": ("01", "匿", "中文隐私处理"), "worddael": ("02", "藏", "切块与原文血缘"),
           "gewita": ("03", "证", "引用格式与引语核对"), "siftan": ("04", "筛", "基准字面重叠筛查"),
           "tellan": ("05", "账", "API 用量对账"), "sothstan": ("06", "审", "模型行为一致性")}


def pretty(value):
    return escape(json.dumps(value, ensure_ascii=False, indent=2))


def render_html(report, chunks):
    cards = []
    for s in report["stages"]:
        number, glyph, name = VOLUMES[s["name"]]
        limits = "".join(f"<li>{escape(line)}</li>" for line in s["limitations"])
        cards.append(f'''<article class="card {s['status']}"><div class="eyebrow">VOLUME {number} / {s['name'].upper()}</div>
<div class="cardtitle"><span class="glyph">{glyph}</span><h2>{name}</h2></div>
<span class="badge {s['status']}">{LABELS[s['status']]}</span><p>{escape(s['summary'])}</p>
<ul class="limits">{limits}</ul><details><summary>展开可重放证据</summary><pre>{pretty(s['evidence'])}</pre></details></article>''')
    rows = []
    for d in report["documents"]:
        rows.append(f"<tr><td>{escape(d['id'])}</td><td>{d['original_characters']:,} → {d['masked_characters']:,}</td><td>{len(d['entities'])}</td><td><code>{d['input_sha256'][:16]}…</code></td><td><details><summary>查看转换血缘</summary><pre>{pretty(d)}</pre></details></td></tr>")
    chunk_rows = []
    for c in chunks:
        chunk_rows.append(f"<details class='chunk'><summary>{escape(c['id'])} <span>脱敏后字符 [{c['start']}, {c['end']})</span></summary><pre class='text'>{escape(c['text'])}</pre><pre>{pretty(c['source_spans'])}</pre></details>")
    missing = [s["name"] for s in report["stages"] if s["status"] == "unavailable"]
    notes = "".join(f"<li>{escape(n)}</li>" for n in report["notes"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'">
<title>六卷书 · 管线证据报告</title><style>
:root{{--ink:#12332e;--muted:#56736c;--line:#d7e4dd;--green:#147660;--paper:#f2f5ed}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--paper);font:15px/1.6 'Segoe UI','Microsoft YaHei',sans-serif}}.wrap{{max-width:1240px;margin:auto;padding:36px}}header{{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:20px}}.brand{{font-size:20px;font-weight:700}}.meta{{font-size:12px;color:var(--muted)}}.hero{{padding:40px 0 30px;display:grid;grid-template-columns:1fr 290px;gap:40px}}.eyebrow{{font-size:11px;letter-spacing:2px;font-weight:650;color:var(--muted)}}h1{{font-size:44px;line-height:1.2;letter-spacing:-1px;margin:12px 0 18px}}.lead{{max-width:760px;color:var(--muted)}}.result{{background:#e0ebe2;border:1px solid #bfd5c8;border-radius:16px;padding:24px}}.result h2{{font-size:27px;margin:12px 0}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}.stat{{border-top:2px solid #aac7b7;padding:14px 0}}.stat strong{{display:block;font-size:28px}}.stat span{{color:var(--muted);font-size:13px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px;min-width:0}}.cardtitle{{display:flex;gap:12px;align-items:center;margin:12px 0}}.glyph{{display:grid;place-items:center;background:#ecf3ed;width:42px;height:42px;border-radius:10px;font-size:23px}}h2{{font-size:18px;margin:0}}.badge{{font-size:11px;border-radius:20px;padding:4px 10px;background:#e0ebe2;color:#286143;font-weight:650}}.badge.unavailable{{background:#eeeae0;color:#7b6638}}.badge.failed,.badge.error{{background:#f8e0dc;color:#9a382f}}.limits{{padding-left:18px;font-size:12px;color:var(--muted)}}.card p{{font-size:14px}}summary{{cursor:pointer;font-size:12px;color:#28644f}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f4f0;padding:12px;border-radius:8px;font-size:11px;color:#234c41;max-height:440px;overflow:auto}}section{{margin-top:36px}}section>h2{{font-size:23px;margin-bottom:16px}}table{{border-collapse:collapse;background:white;width:100%;font-size:12px}}th,td{{text-align:left;padding:13px;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--muted);font-weight:500}}input{{width:100%;padding:12px 16px;border:1px solid #b9d2c3;border-radius:10px;background:#fff;margin-bottom:12px;color:var(--ink)}}.chunk{{padding:12px 16px;background:#fff;border:1px solid var(--line);border-radius:8px;margin:8px 0}}.chunk summary{{font-weight:600;font-size:14px}}.chunk span{{float:right;color:var(--muted);font-size:11px}}.text{{font:14px/1.7 'Microsoft YaHei',sans-serif}}footer{{margin-top:36px;border-top:1px solid var(--line);padding-top:20px;font-size:12px;color:var(--muted)}}code{{word-break:break-all}}@media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}.hero{{grid-template-columns:1fr}}h1{{font-size:34px}}.wrap{{padding:20px}}}}@media(max-width:600px){{.grid{{grid-template-columns:1fr}}.stats{{grid-template-columns:1fr 1fr}}header{{display:block}}table{{display:block;overflow:auto}}}}@media print{{body{{background:white}}.wrap{{padding:0}}.card{{break-inside:avoid}}input{{display:none}}}}
</style></head><body><main class="wrap"><header><div class="brand">六卷书 <span class="meta">THE SIX VOLUMES</span></div><div class="meta">EVIDENCE REPORT · v{report['tool_version']}<br>{escape(report['generated_at'])}</div></header>
<div class="hero"><div><div class="eyebrow">中文知识库 / 从输入到证据</div><h1>每一步，都留下可核对的依据。</h1><p class="lead">脱敏、切块与引用核对在本地完成。污染索引、调用账本和模型基线按实际输入执行；缺失的证据直接展示。原文偏移、转换血缘与内容哈希随报告一起交付。</p><div class="meta">数据口径：<strong>{escape(report['dataset_kind'])}</strong> · 合成演示不代表生产效果</div></div><aside class="result"><div class="eyebrow">本次执行结论</div><h2>{LABELS.get(report['overall'], report['overall'])}</h2><div>通过 {report['status_counts'].get('passed',0)} / 6 卷</div><div class="meta">未提供证据：{escape('、'.join(missing)) or '无'}<br>进程退出码：{report['exit_code']}</div></aside></div>
<div class="stats"><div class="stat"><strong>{len(report['documents'])}</strong><span>导入文档</span></div><div class="stat"><strong>{sum(len(d['entities']) for d in report['documents'])}</strong><span>规则识别并替换的实体</span></div><div class="stat"><strong>{report['chunks']['count']}</strong><span>带原文血缘的切块</span></div><div class="stat"><strong>{report['status_counts'].get('unavailable',0)}</strong><span>明确标注的证据缺口</span></div></div>
<div class="grid">{''.join(cards)}</div><section><h2>文档与来源</h2><table><thead><tr><th>文档</th><th>原文→脱敏字符数</th><th>实体</th><th>原文件 SHA-256</th><th>血缘</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>查看可追溯切块</h2><input id="filter" type="search" placeholder="输入关键词筛选切块" aria-label="筛选切块">{''.join(chunk_rows)}</section>
<footer><strong>如何读这份报告</strong><ul>{notes}</ul><p>完整机器证据：同目录 report.json、chunks.jsonl、artifacts.json。所有偏移均为 Unicode 字符索引，左闭右开。Vault 如保存，位于独立敏感目录，绝不嵌入本报告。</p><p>证据摘要 SHA-256：<code>{report['evidence_sha256']}</code></p></footer></main>
<script>document.getElementById('filter').addEventListener('input',function(){{const q=this.value.toLocaleLowerCase();document.querySelectorAll('.chunk').forEach(e=>e.hidden=!e.textContent.toLocaleLowerCase().includes(q));}});</script></body></html>'''
