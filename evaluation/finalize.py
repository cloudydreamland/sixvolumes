"""Record provenance and assemble a reviewable report from measured results."""
from pathlib import Path
import collections, hashlib, json, os, platform, urllib.request
ROOT=Path(__file__).resolve().parent
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def write(name,obj):(ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SixVolumes-reproducibility-audit/1.0'}),timeout=45) as r:return r.read()

def main():
    modeldir=ROOT/'data/model_license';modeldir.mkdir(exist_ok=True)
    provenance=[]
    for repo in ['BAAI/bge-small-zh-v1.5','Qdrant/bge-small-zh-v1.5']:
        meta=json.loads(fetch('https://huggingface.co/api/models/'+repo));rev=meta['sha'];url=f'https://huggingface.co/{repo}/raw/{rev}/README.md'
        b=fetch(url);p=modeldir/(repo.replace('/','_')+'_README.md');p.write_bytes(b)
        provenance.append({'repo':repo,'revision':rev,'model_card_url':url,'license_declared':meta.get('cardData',{}).get('license'),'model_card_sha256':sha(p)})
    write('data/model_license/provenance.json',provenance)
    # Persist explicit protocol repairs/diagnostic additions without rewriting original protocol.
    write('protocol_amendments.json',{'amendments':[{'change':'Chonkie space delimiter replaced by RecursiveLevel(whitespace=True)','reason':'API rejects whitespace-only custom delimiter; constructor failed before Chonkie results existed','changes_task':False},{'change':'Siftan imported from siftan.index','reason':'README top-level import not exported; module API used; no algorithm changed'},{'change':'nonmember control documents split first20 calibration,next20 holdout','reason':'prevent control-set leakage; done before first successful Siftan run/any threshold or holdout observation'},{'change':'helan_same_normalization diagnostic added','reason':'after observing native Helan failures, same already-used Presidio normalization adapter applied to Helan','claim_restriction':'post-observation diagnostic, NOT independent holdout validation of a product repair'}],'baseline_version_policy':'Pinned disclosed available versions chosen before first results; not claimed latest or comprehensive. Upgrade comparisons require another explicitly labeled run.'})
    rag=read('results/rag_summary.json');pii=[read('results/'+m+'_pii_summary.json') for m in ['helan','presidio_zh_rules','helan_same_normalization']]
    sift=read('results/siftan_summary.json');g=read('results/gewita_online.json');align=read('results/gewita_alignment.json')
    perf=[read('results/'+m+'_performance.json') for m in ['worddael_recursive','langchain_zh_recursive','chonkie_zh_recursive','fixed256']]
    counts=collections.Counter((x['variant'],x['alignment']['level']) for x in align)
    manifest=read('data/manifest.json');modelmanifest=read('results/model_manifest.json')
    onnx=[x for x in modelmanifest['files'] if x['path'].endswith('.onnx')][0]
    rows=['# 六卷书外部公开数据评测报告','',
    '本报告记录同一 AI 协作流程完成的外部数据实验，不是第三方认证或独立人工标注。结果不支持“全面领先主流竞品”或“稳定全国第一”。所有源代码快照、数据来源、逐项输出、错误样例和依赖版本均随本目录保存。',
    '', '## 可引用结果', '',
    '| 切块器 | 原文块数 | 答案跨度 Recall@1 | Recall@3 | Recall@5 |', '|---|---:|---:|---:|---:|']
    for x in rag['rows']:rows.append(f"| {x['method']} | {x['chunks']} | {x['answer_span_recall_at1']:.3%} | {x['answer_span_recall_at3']:.3%} | {x['answer_span_recall_at5']:.3%} |")
    rows.extend(['', '**Worddael 与合理中文配置的 LangChain、Chonkie 在本切片上打平。**固定长度基线的 Recall@1 略高。Worddael 相对固定切块的 Recall@3 高2.101个百分点，按文档重采样的95%区间为[0,4.219]个百分点，不能据此宣称可靠优势。238道题/120篇文章的检索池较小，且只检查检索块是否包含正确原文答案跨度，没有生成答案或语义蕴含评分。', '',
    '| PII实现/配置 | 合成注入精确跨度召回 | 无效格式对照误报 | 说明 |','|---|---:|---:|---|'])
    for x in pii:rows.append(f"| {x['method']} | {x['exact_injection_recall']:.1%} ({round(x['exact_injection_recall']*480)}/480) | {x['negative_control_false_alarms']}/120 | {'看到原生失败后添加的公平诊断对照' if x['method']=='helan_same_normalization' else '冻结配置'} |")
    rows.extend(['','480条为120篇真实CMRC背景×4类脚本构造实体，四种形态各类30条。身份证、手机号、邮箱、银行卡均为合成测试值；不含客户私密资料。原生Helan普通写法均命中；身份证/银行卡空格写法命中；全角、零宽和其他空格写法漏检。该成绩只测构造扰动鲁棒性。不能叫“真实PII召回率”；未穷尽标注自然背景，所以不计算生产精确率。120篇背景两方案均无这四类告警，这也不是背景无PII的证明。', '',
    '**公平性：**Presidio对照是其PatternRecognizer加独立中文模式、校验码、NFKC/空白/零宽映射，不是英文默认配置，也不是完整NER模型。给Helan同一适配器后打平；这隔离出缺口主要在输入规范化。此适配器会删除全部空白，有把无关字符拼接的风险，不能不加约束地当生产安全修复。包装是在看过失败后加入，不属于新的无偏保留集成绩。', '',
    '| Siftan保留样例 | 数量 | 原生精确层告警 | 默认近重复层 | 校准阈值0.15近重复层 |','|---|---:|---:|---:|---:|'])
    for x in sift:
        if x['split']=='holdout':rows.append(f"| {x['kind']} | {x['n']} | {x['exact_flag_rate']:.1%} | {x['near_default_flag_rate']:.1%} | {x['near_calibrated_flag_rate']:.1%} |")
    rows.extend(['','原文、128字截取、全角变体均120/120命中；每10字插入标记时，原生精确层和默认近重复层均0/120；仅用40篇校准得到阈值0.15后，该类120/120被提示。每7字删除1字时各层仍0/120。阈值只是实验侧advisory，未修改Siftan代码。20篇未注入的其他真实文章中3篇触发13-gram重合；这是可能来自共同描述的实际字面重合，不能自动定性为污染，也不能把该构造对照称经人工认证的干净语料。', '',
    '**Gewita：**4篇真实已知DOI通过真实Crossref接口核查为EXISTS；对同一真实记录把年份加5，4条均为SUSPECT。保留4次DOI取元数据与4个标题查询的原始HTTP缓存，库层8次查询调用中同URL复用缓存，整个实验不需要API key。参考文献字符串由真实元数据渲染，不是从论文PDF独立抽取的自然格式样本；不能据此推断普遍文献解析准确率。未调用arXiv兜底，因此不宣称已验证arXiv覆盖。', '',
    '40篇真实文本抽取句子的逐字/全角对齐，以及添加“并非”的词面反例，结果分类：`'+str(dict(counts))+'`。加否定仍可能被近似对齐识别，这不是证明来源支持该否定论断。此探针不是人工语义金标。', '',
    '## 实验约束与权利来源','',
    '- CMRC2018官方仓库，冻结提交 `'+manifest['cmrc_commit']+'`，CC BY-SA 4.0。原始数据集和本目录的语料衍生文件按同许可保留署名/来源；原文、题目和答案源自发布方，未重新声称人工标注。',
    '- 从公开dev集选择原文长度>=256且有合法答案偏移的样本，先按标题聚合，每标题取一个固定段落，再按SHA256排序：40校准、120保留、40非成员对照（前20用于校准，后20用于保留）。标题隔离避免同篇文章跨集合。它是本地实验划分，不是官方CMRC test榜单。',
    '- 所有切块器均以256 Unicode字符、0重叠为目标。LangChain显式中文标点/保留分隔符/不裁空白；Chonkie显式中文递归规则/character计数。没有在保留结果上搜索切块参数。Worddael因标点吸附产生4个257字块，已记录预算违反，其他方案无超限。',
    '- 向量模型：BAAI/bge-small-zh-v1.5，FastEmbed使用Qdrant ONNX转换，CPU 2线程，512维。模型卡声明MIT，卡片版本和SHA256见 `data/model_license/provenance.json`。训练语料是否包含CMRC未审计，因此不声称模型对CMRC无训练污染；所有切块器共用同一模型。',
    '- ONNX文件 '+str(onnx['bytes'])+' bytes，SHA256 `'+onnx['sha256']+'`。文件为数值模型推理，未执行远程Python代码。模型加载后评测可离线复跑。',
    '- Crossref缓存是公开接口响应，仅用于本地审计重放。事实性书目信息与HTTP响应中可能包含的第三方摘要权利有别，不把整个响应宣称为MIT或CC0；公开发布前应只导出必要书目字段，保留来源。',
    '- 版本：langchain-text-splitters 1.0.0、chonkie 1.3.1、presidio-analyzer 2.2.360、fastembed 0.7.3；完整传递依赖见 `requirements.lock.txt`。它们是明确冻结版本，不宣称截至今日最新。四个自有库以 `source_snapshot` 哈希为准，不替远端仓库承诺相同提交。',
    '', '## 时间与内存','',
    '| 切块器 | 120篇切块耗时ms | 采样进程RSS峰值MB | Python临时分配峰值MB | 偏移错误/未覆盖字符 |', '|---|---:|---:|---:|---|'])
    for x in perf:rows.append(f"| {x['method']} | {x['elapsed_ms']:.2f} | {x['rss_peak_mb']:.2f} | {x['python_alloc_peak_mb']:.3f} | {x['offset_errors']} / {x['uncovered_chars']} |")
    rows.extend(['','每种方案独立子进程；导入后计时，5ms间隔采样RSS，tracemalloc只测Python分配（会影响耗时），单次运行，未隔离整机其他负载。RSS包括已加载依赖，不能把单次毫秒差当严格性能排名。四个切块器偏移检查均通过。', '',
    '## 复现与复核','',
    '已有环境：运行 `./replay.ps1`，将自动建立新的 results_replay_时间戳 目录，保留原始results不变。新环境运行 `python -m venv .venv`，安装 `requirements.lock.txt`，随后运行 `download_model.py` 和 `replay.ps1`。源码/数据快照已附，无需重新运行prepare.py；prepare.py会重新取得上游master状态，仅用于重建新版本数据，不能冒称原冻结实验。原结果对应的执行代码已另存 executed_run_20261023.py，其哈希与results/environment.json一致；run.py只增加结果目录保护，没有修改算法或样例。',
    '',
    '入口说明：`run.py rag`仅重跑向量检索；`run.py siftan`重跑污染筛查；`run.py gewita`用原始HTTP缓存重放；`run.py pii-worker helan`重跑原生PII。`verify_integrity.py`核查SHA256。`results/*_errors.json`保存漏检/偏移错误；完整逐题top5和来源片段见 `rag_details.json`。', '',
    '缺口仍在：未获得真实客户PII人工标注、跨行业外部复用反馈、真实API账单或模型替换审计数据；没有把缺失证据填成通过。要对修复版本提出泛化结论，需另行冻结新的语料/扰动设计，并由未参与开发的人复核标签。', ''])
    (ROOT/'评测报告.md').write_text('\n'.join(rows),encoding='utf-8')
    write('results/key_findings.json',{'rag':rag,'pii':[{k:v for k,v in r.items() if k not in ['groups']} for r in pii],'siftan':sift,'gewita':{'real_records':4,'real_statuses':[r['actual']['status'] for r in g['rows'] if r.get('variant')=='authentic_metadata'],'modified_year_statuses':[r['actual']['status'] for r in g['rows'] if r.get('variant')=='synthetic_year_plus5']},'model_license':provenance,'dataset_commit':manifest['cmrc_commit'],'machine':{'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count()}})
    exclusions={'.venv','pip-cache','tmp','__pycache__'}
    files=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(ROOT.rglob('*')) if p.is_file() and not any(part in exclusions for part in p.relative_to(ROOT).parts) and p.name!='SHA256SUMS.json']
    write('SHA256SUMS.json',files)
    print(json.dumps({'report':'评测报告.md','manifest_files':len(files),'model_provenance':provenance},ensure_ascii=False))
if __name__=='__main__':main()
