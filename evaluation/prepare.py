"""Freeze public data and source before evaluation. Only writes beside this file."""
from pathlib import Path
import json, hashlib, urllib.request, shutil, datetime, sys

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
def save(name,obj): (DATA/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'SixVolumes-independent-evaluation/1.0 (small academic audit)'})
    with urllib.request.urlopen(req,timeout=90) as r: return r.read()

def main():
    api=json.loads(fetch('https://api.github.com/repos/ymcui/cmrc2018/commits/master'))
    commit=api['sha']; manifest=[]
    for name in ['squad-style-data/cmrc2018_dev.json','LICENCE','README.md']:
        url=f'https://raw.githubusercontent.com/ymcui/cmrc2018/{commit}/{name}'
        b=fetch(url); dest=DATA/('cmrc2018_'+Path(name).name if name!='squad-style-data/cmrc2018_dev.json' else 'cmrc2018_dev.json')
        dest.write_bytes(b); manifest.append({'path':str(dest.relative_to(ROOT)), 'url':url,'sha256':sha(b),'bytes':len(b),'license':'CC-BY-SA-4.0'})
    raw=json.loads((DATA/'cmrc2018_dev.json').read_text(encoding='utf-8'))
    records=[]
    for a in raw['data']:
        for p in a['paragraphs']:
            text=p['context']; qs=[]
            for q in p['qas']:
                answers=[v for v in q['answers'] if text[v['answer_start']:v['answer_start']+len(v['text'])]==v['text']]
                if answers: qs.append({'id':q['id'],'question':q['question'],'answers':answers})
            if len(text)>=256 and qs:
                records.append({'id':sha(text.encode())[:16],'title':a.get('title',''), 'text':text,'qas':qs})
    # Deduplicate contexts then split by title, not by questions.
    records=list({r['id']:r for r in records}.values())
    groups={}
    for r in records: groups.setdefault(r['title'],[]).append(r)
    titles=sorted(groups,key=lambda s:sha(('20261023|'+s).encode()))
    selected=[]
    for i,t in enumerate(titles[:200]):
        r=sorted(groups[t],key=lambda r:r['id'])[0]
        r['split']='calibration' if i<40 else 'holdout' if i<160 else 'nonmember_control'
        selected.append(r)
    save('documents.json',selected)
    manifest.append({'path':'data/documents.json','sha256':sha((DATA/'documents.json').read_bytes()),'derived_from':'cmrc2018_dev.json','license':'CC-BY-SA-4.0','selection':'one paragraph per title; titles SHA256(20261023|title) sorted; first40 calibration,next120 holdout,next40 nonmember control; len>=256 and valid answer offsets'})
    snapshot=ROOT/'source_snapshot'; snapshot.mkdir(exist_ok=True)
    old=Path('E:/AIC/output/competition_audit_20261023_open_source')
    names={'helan':'TheVeilOfHiddenNames','worddael':'TheDaleOfRememberedWords','gewita':'WitnessesInTheMargins','siftan':'TheSieveBeneathTheStars'}
    for pkg,repo in names.items():
        src=old/(repo+'-main')
        dst=snapshot/pkg
        if not dst.exists():
            dst.mkdir();shutil.copytree(src/'src',dst/'src',ignore=shutil.ignore_patterns('__pycache__'))
            for f in ['LICENSE','pyproject.toml']:
                if (src/f).exists():shutil.copy2(src/f,dst/f)
        files=[{'path':str(p.relative_to(ROOT)), 'sha256':sha(p.read_bytes())} for p in sorted(dst.rglob('*')) if p.is_file() and '__pycache__' not in str(p)]
        manifest.append({'package':pkg,'repository':'https://github.com/cloudydreamland/'+repo,'source':'local audit source snapshot; content hashes authoritative, no remote commit claimed','files':files})
    save('manifest.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cmrc_commit':commit,'sources':manifest})
    protocol={'protocol_version':'1.0-before-first-run','split_counts':{k:sum(x['split']==k for x in selected) for k in ['calibration','holdout','nonmember_control']},'worddael':{'chunk_char_budget':256,'overlap':0,'k':[1,3,5],'max_questions_per_document':2,'metric':'gold answer span contained in retrieved chunk from the correct original document; original CMRC labels; not generated-answer quality','model':'BAAI/bge-small-zh-v1.5 via FastEmbed CPU ONNX, fixed for every splitter'},'helan':{'labels':'independent deterministic injection; NOT human labels or real customer PII','types':['ID_CARD','PHONE','EMAIL','BANK_CARD'],'variants':['plain','fullwidth','spaced','zero_width'],'negative_controls':['invalid checksum','invalid mobile prefix','ordinary numerical code'],'report_scope':'typed exact spans; no PERSON/ADDRESS/semantic PII claims'},'siftan':{'positive_cases':['exact','partial128','fullwidth','insert_every10','delete_every7'],'negative_label':'nonmember_control, not certified uncontaminated','threshold_grid':[0.05,0.1,0.15,0.2,0.25,0.3,0.4,0.5],'calibration':'maximize F1 on calibration only; tie choose higher threshold; frozen before holdout','near_dup_advisory_only':True},'gewita':{'source_queries':'at most 8 known real DOI works and arXiv metadata; cache raw responses; structured modified-year controls are synthetic','quote_alignment':'real CMRC excerpts + deterministic normalization/negation transformations; negation is NOT human semantic annotation'},'honesty':['No external human review claimed','No API bill/customer data','No post-holdout parameter optimization','All failures retained','Synthetic perturbation labels do not measure production accuracy']}
    (ROOT/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'documents':len(selected),'splits':protocol['split_counts'],'commit':commit},ensure_ascii=False))

if __name__=='__main__':main()
