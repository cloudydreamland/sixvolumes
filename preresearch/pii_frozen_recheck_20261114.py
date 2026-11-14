# -*- coding: utf-8 -*-
"""冻结评测集回归复测（2026-11-14）：用修复后的 vendor/helan 在 10-23 冻结评测集上复测。
协议与判定逻辑逐条复刻 evaluation/run.py 的 pii 阶段（native 与 same_normalization 两种视图），
数据用冻结的 pii_injections.json / pii_negative_controls.json / documents.json，不改动任何冻结文件。"""
import json, sys, time, unicodedata
from pathlib import Path

ENG = Path(r"E:\AIC\双赛道补强_20261023\开源\工程\evaluation")
sys.path.insert(0, str(Path(r"E:\AIC\双赛道补强_20261023\开源\工程\vendor\helan\src")))
from helan import recognize  # noqa: E402

TYPES = ['ID_CARD', 'PHONE', 'EMAIL', 'BANK_CARD']
injections = json.loads((ENG / 'data/pii_injections.json').read_text(encoding='utf-8'))
controls = json.loads((ENG / 'data/pii_negative_controls.json').read_text(encoding='utf-8'))
docs = json.loads((ENG / 'data/documents.json').read_text(encoding='utf-8'))

def native(t):
    return [{'type': e.type, 'start': e.start, 'end': e.end, 'text': e.text}
            for e in recognize(t, types=TYPES)]

def wrapped(t):
    chars, idx = [], []
    for i, c in enumerate(t):
        for v in unicodedata.normalize('NFKC', c):
            if not v.isspace() and v != '\u200b':
                chars.append(v); idx.append(i)
    out = []
    for e in native(''.join(chars)):
        start, end = idx[e['start']], idx[e['end'] - 1] + 1
        out.append({'type': e['type'], 'start': start, 'end': end, 'text': t[start:end]})
    return out

def run(method_name, det):
    rows, cr, bg = [], [], []
    t0 = time.perf_counter()
    for r in injections:
        preds = det(r['text'])
        hit = any(p['type'] == r['type'] and p['start'] == r['gold'][0] and p['end'] == r['gold'][1] for p in preds)
        rows.append(hit)
    # 与冻结协议逐字一致：对照误报按声明类型判定（run.py pii_worker 内 cr 构建）
    for c in controls:
        cr.append(any(p['type'] == c['type'] for p in det(c['text'])))
    for d in docs:
        bg.append(bool(det(d['text'])))
    dt = time.perf_counter() - t0
    return {
        'method': method_name,
        'injections': len(rows),
        'exact_injection_recall': sum(rows) / len(rows),
        'negative_controls': len(cr),
        'negative_control_false_alarms': sum(cr),
        'unannotated_background_alerts': sum(bg),
        'elapsed_s_recheck': round(dt, 3),
        'missed_ids': [r['id'] for r, ok in zip(injections, rows) if not ok][:20],
    }

out = {'frozen_baseline': {}, 'recheck_20261114_fixed_helan': {}}
for m, summary in [('helan', 'helan_pii_summary.json'), ('helan_same_normalization', 'helan_same_normalization_pii_summary.json')]:
    p = ENG / 'results' / summary
    if p.exists():
        s = json.loads(p.read_text(encoding='utf-8'))
        out['frozen_baseline'][m] = {k: s[k] for k in ('injections', 'exact_injection_recall', 'negative_controls', 'negative_control_false_alarms', 'unannotated_background_alerts')}
out['recheck_20261114_fixed_helan']['helan'] = run('helan', native)
out['recheck_20261114_fixed_helan']['helan_same_normalization'] = run('helan_same_normalization', wrapped)
print(json.dumps(out, ensure_ascii=False, indent=1))
Path(__file__).with_name('recheck_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
