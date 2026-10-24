"""Reproducible external-data evaluation. No API keys, no changes to subject packages."""
from pathlib import Path
import argparse, csv, dataclasses, hashlib, importlib.metadata, json, math, os, re, statistics, subprocess, sys, threading, time, tracemalloc, unicodedata, urllib.parse, urllib.request

ROOT=Path(__file__).resolve().parent
for package in ['helan','worddael','gewita','siftan']:
    sys.path.insert(0,str(ROOT/'source_snapshot'/package/'src'))
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
RESULT=(ROOT/os.environ.get('SIXVOLUMES_RESULTS','results')).resolve()
if not RESULT.is_relative_to(ROOT):raise ValueError('Results must stay inside this evaluation directory')
RESULT.mkdir(exist_ok=True)
DOCS=json.loads((ROOT/'data/documents.json').read_text(encoding='utf-8'))
def digest(b):return hashlib.sha256(b).hexdigest()
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def table(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def measured(fn):
    import psutil
    proc=psutil.Process();samples=[proc.memory_info().rss];stop=threading.Event()
    def sampler():
        while not stop.wait(.005):samples.append(proc.memory_info().rss)
    th=threading.Thread(target=sampler);th.start();tracemalloc.start();t=time.perf_counter()
    try:out=fn()
    finally:
        elapsed=time.perf_counter()-t;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();samples.append(proc.memory_info().rss);stop.set();th.join()
    return out,{'elapsed_ms':elapsed*1000,'rss_peak_mb':max(samples)/2**20,'rss_start_mb':samples[0]/2**20,'python_alloc_peak_mb':peak/2**20,'memory_note':'isolated worker RSS sampled every5ms after imports; Python allocations via tracemalloc; timing includes instrumentation'}

METHODS=['worddael_recursive','langchain_zh_recursive','chonkie_zh_recursive','fixed256']
def splitter(method):
    if method=='worddael_recursive':
        from worddael import RecursiveChunker
        obj=RecursiveChunker(max_chars=256,overlap_chars=0)
        return lambda t:[{'text':c.text,'start':c.start,'end':c.end} for c in obj.chunk(t)]
    if method=='langchain_zh_recursive':
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        obj=RecursiveCharacterTextSplitter(chunk_size=256,chunk_overlap=0,length_function=len,add_start_index=True,strip_whitespace=False,keep_separator='end',separators=['\n\n','\n','。','！','？','；','，','、',' ',''])
        return lambda t:[{'text':c.page_content,'start':c.metadata['start_index'],'end':c.metadata['start_index']+len(c.page_content)} for c in obj.create_documents([t])]
    if method=='chonkie_zh_recursive':
        from chonkie import RecursiveChunker,RecursiveRules,RecursiveLevel
        rules=RecursiveRules(levels=[RecursiveLevel(delimiters=['\n\n','\n']),RecursiveLevel(delimiters=['。','！','？','；']),RecursiveLevel(delimiters=['，','、']),RecursiveLevel(whitespace=True),RecursiveLevel()])
        obj=RecursiveChunker(tokenizer_or_token_counter='character',chunk_size=256,rules=rules,min_characters_per_chunk=1)
        return lambda t:[{'text':c.text,'start':c.start_index,'end':c.end_index} for c in obj.chunk(t)]
    return lambda t:[{'text':t[i:i+256],'start':i,'end':min(i+256,len(t))} for i in range(0,len(t),256)]

def chunk_worker(method):
    fn=splitter(method);docs=[d for d in DOCS if d['split']=='holdout']
    def execute():
        out=[]
        for d in docs:
            for c in fn(d['text']):c['doc_id']=d['id'];out.append(c)
        return out
    chunks,perf=measured(execute)
    source={d['id']:d['text'] for d in docs};errors=[]
    for i,c in enumerate(chunks):
        if c['start']<0 or source[c['doc_id']][c['start']:c['end']]!=c['text']:errors.append({'chunk':i,**c})
    noncovered=0;totalchars=0
    for d in docs:
        coverage=set()
        for c in chunks:
            if c['doc_id']==d['id'] and c['start']>=0:coverage.update(range(c['start'],c['end']))
        noncovered+=len(d['text'])-len(coverage);totalchars+=len(d['text'])
    perf.update({'method':method,'documents':len(docs),'chunks':len(chunks),'chars':totalchars,'offset_errors':len(errors),'uncovered_chars':noncovered,'oversize_chunks':sum(len(c['text'])>256 for c in chunks),'max_chunk_chars':max(map(lambda c:len(c['text']),chunks))})
    dump(RESULT/(method+'_chunks.json'),chunks);dump(RESULT/(method+'_performance.json'),perf);dump(RESULT/(method+'_offset_errors.json'),errors)
    print(json.dumps(perf))

def rag():
    import numpy as np
    from fastembed import TextEmbedding
    docs=[d for d in DOCS if d['split']=='holdout'];questions=[]
    for d in docs:
        for q in d['qas'][:2]:questions.append({**q,'doc_id':d['id']})
    m=TextEmbedding('BAAI/bge-small-zh-v1.5',cache_dir=str(ROOT/'models'),threads=2,local_files_only=True)
    start=time.perf_counter();qvec=np.array(list(m.query_embed([q['question'] for q in questions],batch_size=32)))
    summary=[];details=[]
    for method in METHODS:
        chunks=json.loads((RESULT/(method+'_chunks.json')).read_text(encoding='utf-8'))
        t=time.perf_counter();vec=np.array(list(m.passage_embed([c['text'] for c in chunks],batch_size=32)));embed_s=time.perf_counter()-t
        sims=qvec@vec.T;ranks=np.argsort(-sims,axis=1,kind='stable')[:,:5]
        hits={1:0,3:0,5:0};mrr=0
        for qi,q in enumerate(questions):
            correct=[]
            for rank,ci in enumerate(ranks[qi],1):
                c=chunks[int(ci)]
                ok=c['doc_id']==q['doc_id'] and any(c['start']<=a['answer_start'] and c['end']>=a['answer_start']+len(a['text']) for a in q['answers'])
                if ok:correct.append(rank)
            first=min(correct) if correct else None;mrr+=(1/first if first else 0)
            for k in hits:hits[k]+=bool(first and first<=k)
            details.append({'method':method,'question_id':q['id'],'doc_id':q['doc_id'],'question':q['question'],'answers':q['answers'],'first_correct_rank':first,'top5':[{'rank':i+1,'similarity':float(sims[qi,ci]),**chunks[int(ci)]} for i,ci in enumerate(ranks[qi])]})
        row={'method':method,'questions':len(questions),'chunks':len(chunks),'embedding_seconds':embed_s,'mrr_at5':mrr/len(questions),**{f'answer_span_recall_at{k}':v/len(questions) for k,v in hits.items()}}
        summary.append(row);print(json.dumps(row),flush=True)
    # Paired bootstrap by document, preserving multiple questions from a document.
    base=METHODS[0];comparisons=[];rng=np.random.default_rng(20261023)
    by={(r['method'],r['question_id']):int(bool(r['first_correct_rank'] and r['first_correct_rank']<=3)) for r in details}
    for other in METHODS[1:]:
        perdoc=[]
        for d in docs:
            vals=[by[(base,q['id'])]-by[(other,q['id'])] for q in d['qas'][:2]]
            perdoc.append(vals)
        boot=[]
        for _ in range(2000):
            selected=rng.integers(0,len(perdoc),len(perdoc));vals=[v for i in selected for v in perdoc[i]];boot.append(sum(vals)/len(vals))
        diff=(sum(by[(base,q['id'])]-by[(other,q['id'])] for q in questions))/len(questions)
        comparisons.append({'baseline':other,'metric':'recall@3 difference worddael-baseline','difference':diff,'document_bootstrap_95ci':[float(v) for v in np.quantile(boot,[.025,.975])],'resamples':2000})
    dump(RESULT/'rag_summary.json',{'rows':summary,'paired_document_bootstrap':comparisons,'total_seconds':time.perf_counter()-start,'note':'Real public CMRC questions and answer spans, CPU learned ONNX embeddings. Retrieval only; no generation or LLM judge.'})
    dump(RESULT/'rag_details.json',details);table(RESULT/'rag_summary.csv',summary);dump(RESULT/'rag_errors.json',[r for r in details if r['first_correct_rank'] is None])

def fullwidth(s):return ''.join(chr(ord(c)+0xFEE0) if 33<=ord(c)<=126 else c for c in s)
def idcheck(s):
    if not re.fullmatch(r'\d{17}[\dXx]',s):return False
    try:
        import datetime
        datetime.datetime.strptime(s[6:14],'%Y%m%d')
    except ValueError:return False
    weights=[7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
    return s[-1].upper()=='10X98765432'[sum(int(x)*w for x,w in zip(s[:17],weights))%11]
def luhn(s):
    total=0
    for i,x in enumerate(reversed(s)):
        n=int(x)*(2 if i%2 else 1);total+=n-9 if n>9 else n
    return total%10==0
def synth_value(kind,i):
    if kind=='ID_CARD':
        body='11010519870312'+f'{i%999:03d}';return body+next(x for x in '0123456789X' if idcheck(body+x))
    if kind=='BANK_CARD':
        body='622202'+f'{i:09d}';return body+next(str(x) for x in range(10) if luhn(body+str(x)))
    if kind=='PHONE':return '138'+f'{i:08d}'
    return f'audit{i}@example.com'

def make_pii():
    out=[];types=['ID_CARD','PHONE','EMAIL','BANK_CARD'];labels={'ID_CARD':'身份证','PHONE':'手机号','EMAIL':'电子邮箱','BANK_CARD':'银行卡'}
    for i,d in enumerate([x for x in DOCS if x['split']=='holdout']):
        for k,kind in enumerate(types):
            raw=synth_value(kind,100+i);variant=['plain','fullwidth','spaced','zero_width'][(i+k)%4]
            token=raw if variant=='plain' else fullwidth(raw) if variant=='fullwidth' else ' '.join(raw[j:j+4] for j in range(0,len(raw),4)) if variant=='spaced' else '\u200b'.join(raw[j:j+4] for j in range(0,len(raw),4))
            prefix=d['text']+'\n【合成测试字段】'+labels[kind]+'：';text=prefix+token+'。'
            out.append({'id':f'{d["id"]}-{kind}','doc_id':d['id'],'type':kind,'variant':variant,'text':text,'gold':[len(prefix),len(prefix)+len(token)],'annotation':'scripted injection only; background is not exhaustively human-annotated'})
    dump(ROOT/'data/pii_injections.json',out)
    controls=[]
    for i in range(40):
        idv=synth_value('ID_CARD',200+i);bad=idv[:-1]+('0' if idv[-1]!='0' else '1')
        bank=synth_value('BANK_CARD',200+i);bankbad=bank[:-1]+str((int(bank[-1])+1)%10)
        controls.extend([{'id':f'invalid_id_{i}','text':'此为无效校验码测试：身份证 '+bad+'。','type':'ID_CARD'}, {'id':f'invalid_bank_{i}','text':'此为无效校验码测试：银行卡 '+bankbad+'。','type':'BANK_CARD'}, {'id':f'invalid_phone_{i}','text':'此为无效号段测试：手机号 111'+f'{i:08d}'+'。','type':'PHONE'}])
    dump(ROOT/'data/pii_negative_controls.json',controls)
    return out,controls

def pii_detector(method):
    if method in ['helan','helan_same_normalization']:
        from helan import recognize
        native=lambda t:[{'type':e.type,'start':e.start,'end':e.end,'text':e.text} for e in recognize(t,types=['ID_CARD','PHONE','EMAIL','BANK_CARD'])]
        if method=='helan':return native
        def wrapped(t):
            chars=[];idx=[]
            for i,c in enumerate(t):
                for v in unicodedata.normalize('NFKC',c):
                    if not v.isspace() and v!='\u200b':chars.append(v);idx.append(i)
            out=[]
            for e in native(''.join(chars)):
                start,end=idx[e['start']],idx[e['end']-1]+1
                out.append({'type':e['type'],'start':start,'end':end,'text':t[start:end]})
            return out
        return wrapped
    from presidio_analyzer import PatternRecognizer,Pattern
    class Checked(PatternRecognizer):
        def validate_result(self,s):
            if self.supported_entities[0]=='ID_CARD':return idcheck(s)
            if self.supported_entities[0]=='BANK_CARD':return luhn(s)
            return None
    patterns={'ID_CARD':r'(?<![0-9])[1-9][0-9]{16}[0-9Xx](?![0-9])','PHONE':r'(?<![0-9])1[3-9][0-9]{9}(?![0-9])','BANK_CARD':r'(?<![0-9])6[0-9]{15,18}(?![0-9])','EMAIL':r'(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![A-Za-z0-9])'}
    recognizers=[Checked(supported_entity=k,patterns=[Pattern(k,v,.7)],supported_language='zh') for k,v in patterns.items()]
    def fn(t):
        # General Chinese normalization adapter, fixed before evaluation. No Helan code reused.
        chars=[];idx=[]
        for i,c in enumerate(t):
            for v in unicodedata.normalize('NFKC',c):
                if not v.isspace() and v!='\u200b':chars.append(v);idx.append(i)
        n=''.join(chars);out=[]
        for r in recognizers:
            for e in r.analyze(n,r.supported_entities):
                if e.score<=0:continue
                start,end=idx[e.start],idx[e.end-1]+1
                out.append({'type':e.entity_type,'start':start,'end':end,'text':t[start:end]})
        return out
    return fn

def pii_worker(method):
    data=json.loads((ROOT/'data/pii_injections.json').read_text(encoding='utf-8'));controls=json.loads((ROOT/'data/pii_negative_controls.json').read_text(encoding='utf-8'));fn=pii_detector(method)
    def execute():
        rows=[]
        for r in data:
            pred=fn(r['text']);hit=any(e['type']==r['type'] and [e['start'],e['end']]==r['gold'] for e in pred)
            unexpected=[e for e in pred if [e['start'],e['end']]!=r['gold']]
            rows.append({'method':method,'id':r['id'],'type':r['type'],'variant':r['variant'],'hit':hit,'predictions':pred,'gold':r['gold'],'unexpected':unexpected})
        return rows
    rows,perf=measured(execute);cr=[]
    for r in controls:
        pred=[e for e in fn(r['text']) if e['type']==r['type']];cr.append({**r,'predictions':pred,'false_alarm':bool(pred)})
    originals=[{'doc_id':d['id'],'predictions':fn(d['text'])} for d in DOCS if d['split']=='holdout']
    groups=[]
    for kind in ['ID_CARD','PHONE','EMAIL','BANK_CARD']:
        for var in ['plain','fullwidth','spaced','zero_width']:
            ss=[x for x in rows if x['type']==kind and x['variant']==var];groups.append({'method':method,'type':kind,'variant':var,'n':len(ss),'exact_injection_recall':sum(x['hit'] for x in ss)/len(ss)})
    summary={'method':method,'injections':len(rows),'exact_injection_recall':sum(r['hit'] for r in rows)/len(rows),'negative_controls':len(cr),'negative_control_false_alarms':sum(r['false_alarm'] for r in cr),'unannotated_background_alerts':sum(bool(r['predictions']) for r in originals),'performance':perf,'groups':groups,'scope':'4 structured entity types, synthetic injections; NOT production PII accuracy; background alerts require human adjudication; baseline is Presidio PatternRecognizer+independent Chinese normalizer/checksums, NOT full Presidio NER'}
    dump(RESULT/(method+'_pii_summary.json'),summary);dump(RESULT/(method+'_pii_details.json'),{'injections':rows,'negative_controls':cr,'background_alerts':originals});table(RESULT/(method+'_pii_groups.csv'),groups);dump(RESULT/(method+'_pii_errors.json'),[r for r in rows if not r['hit'] or r['unexpected']]);print(json.dumps(summary,ensure_ascii=False),flush=True)

def sift():
    from siftan import screen
    from siftan.index import build_index
    control=[d for d in DOCS if d['split']=='nonmember_control'];allrows=[];summ=[];threshold=None
    for split in ['calibration','holdout']:
        docs=[d for d in DOCS if d['split']==split];index=build_index([d['text'] for d in docs],name='CMRC2018-'+split);samples=[]
        for d in docs:
            t=d['text'];cases={'exact':t,'partial128':t[len(t)//3:len(t)//3+128],'fullwidth':fullwidth(t),'insert_every10':'（测试插入）'.join(t[i:i+10] for i in range(0,len(t),10)),'delete_every7':''.join(c for i,c in enumerate(t) if i%7!=0)}
            for kind,value in cases.items():samples.append({'id':d['id']+'-'+kind,'doc_id':d['id'],'text':value,'kind':kind,'injected':True})
        # Controls are also disjoint across calibration and holdout.
        for d in (control[:20] if split=='calibration' else control[20:]):samples.append({'id':d['id']+'-control','doc_id':d['id'],'text':d['text'],'kind':'nonmember_control','injected':False})
        cert,perf=measured(lambda:screen('external-'+split,[(r['id'],r['text']) for r in samples],index))
        for r,v in zip(samples,cert.records):r.update({'split':split,'exact_hits':v.hits,'exact_flagged':v.flagged,'near_ratio':v.near_dup_ratio or 0,'near_default_flagged':v.near_dup_hit,'matched_ngrams':v.samples})
        if split=='calibration':
            grid=[]
            for th in [.05,.1,.15,.2,.25,.3,.4,.5]:
                tp=sum(r['injected'] and r['near_ratio']>=th for r in samples);fp=sum(not r['injected'] and r['near_ratio']>=th for r in samples);fn=sum(r['injected'] and r['near_ratio']<th for r in samples);f1=2*tp/max(1,2*tp+fp+fn);grid.append({'threshold':th,'f1_on_constructed_membership':f1,'tp':tp,'fp':fp,'fn':fn})
            threshold=max(grid,key=lambda r:(r['f1_on_constructed_membership'],r['threshold']))['threshold'];dump(RESULT/'siftan_calibration_frozen.json',{'threshold':threshold,'grid':grid,'note':'nonmember != guaranteed clean. F1 here evaluates constructed membership only; not semantic contamination.'})
        for kind in sorted(set(r['kind'] for r in samples)):
            sub=[r for r in samples if r['kind']==kind];summ.append({'split':split,'kind':kind,'n':len(sub),'exact_flag_rate':sum(r['exact_flagged'] for r in sub)/len(sub),'near_default_flag_rate':sum(r['near_default_flagged'] for r in sub)/len(sub),'near_calibrated_flag_rate':sum(r['near_ratio']>=threshold for r in sub)/len(sub),'calibrated_threshold':threshold})
        allrows.extend(samples);dump(RESULT/('siftan_'+split+'_performance.json'),perf)
    dump(RESULT/'siftan_summary.json',summ);table(RESULT/'siftan_summary.csv',summ);dump(RESULT/'siftan_details.json',allrows);print(json.dumps(summ,ensure_ascii=False))

def live_fetch(url,cache_dir):
    cache_dir.mkdir(exist_ok=True);key=digest(url.encode());path=cache_dir/(key+'.json')
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    req=urllib.request.Request(url,headers={'User-Agent':'SixVolumesExternalAudit/1.0 (small reproducibility audit)'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:record={'url':url,'status':r.status,'body':r.read().decode('utf-8','replace'),'fetched_unix':time.time()}
    except Exception as e:record={'url':url,'status':0,'body':'','error':str(e),'fetched_unix':time.time()}
    record['body_sha256']=digest(record['body'].encode());dump(path,record);time.sleep(1.1);return record

def gewita():
    from gewita import parse_references,align_quote
    from gewita.existence import verify_online,TransportResponse,QueryBudget
    from gewita.refs import Reference
    cache=ROOT/'data/http_cache';works=[]
    for doi in ['10.18653/v1/D19-1600','10.18653/v1/N19-1423','10.18653/v1/2023.emnlp-main.398','10.1109/TWC.2024.3454073']:
        rec=live_fetch('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''),cache)
        if rec['status']==200:
            m=json.loads(rec['body'])['message'];works.append({'doi':doi,'title':m['title'][0],'year':m['issued']['date-parts'][0][0],'venue':(m.get('container-title') or [''])[0],'authors':m.get('author',[])})
        else:works.append({'doi':doi,'fetch_error':rec.get('error',str(rec['status']))})
    dump(ROOT/'data/real_crossref_works.json',works)
    def transport(url):
        rec=live_fetch(url,cache);return TransportResponse(rec['status'],rec['body'])
    budget=QueryBudget(min_interval=1.1,max_queries=16,max_retries=0);rows=[]
    for i,w in enumerate(works,1):
        if 'fetch_error' in w:rows.append(w);continue
        authors='，'.join(a.get('family','')+' '+a.get('given','') for a in w['authors'][:3])
        text=f'[{i}] {authors}. {w["title"]}[J]. {w["venue"]}, {w["year"]}. DOI:{w["doi"]}.'
        parsed=parse_references(text,assume_section=True)
        for variant,year in [('authentic_metadata',w['year']),('synthetic_year_plus5',w['year']+5)]:
            ref=Reference(index=i,raw=text,span=(0,len(text)),title=w['title'],year=year,venue=w['venue'],doi=w['doi'],parsed=True)
            result=verify_online(ref,transport=transport,_budget=budget)
            rows.append({'doi':w['doi'],'variant':variant,'expected':'EXISTS' if variant=='authentic_metadata' else 'SUSPECT','actual':dataclasses.asdict(result),'rendered_reference':text,'rendering_note':'GB/T-like rendering generated from real metadata, not a naturally occurring citation string','parse_result':[dataclasses.asdict(p) for p in parsed],'title_parse_exact':bool(parsed and parsed[0].title==w['title']),'year_parse_exact':bool(parsed and parsed[0].year==w['year'])})
    aligns=[]
    for d in [r for r in DOCS if r['split']=='holdout'][:40]:
        match=re.search(r'[^。！？\n]{20,100}[。！？]',d['text'])
        if not match:continue
        quote=match.group();variants={'verbatim':quote,'fullwidth':fullwidth(quote),'negation_probe':'并非'+quote}
        for v,q in variants.items():
            a=align_quote(q,d['text']);aligns.append({'doc_id':d['id'],'variant':v,'quote':q,'alignment':dataclasses.asdict(a),'expected_scope':'verbatim/fullwidth test localization; negation_probe is an adversarial surface-overlap example, NOT a semantic gold label'})
    dump(RESULT/'gewita_online.json',{'rows':rows,'query_budget_used':budget.used,'note':'Cached real network responses. Network failures stay UNVERIFIED; absent metadata does not establish nonexistent publication.'});dump(RESULT/'gewita_alignment.json',aligns)
    table(RESULT/'gewita_online.csv',[{'doi':r['doi'],'variant':r.get('variant','fetch_error'),'expected':r.get('expected'),'status':r.get('actual',{}).get('status'),'detail':r.get('actual',{}).get('detail',r.get('fetch_error')),'title_parse_exact':r.get('title_parse_exact'),'year_parse_exact':r.get('year_parse_exact')} for r in rows]);print(json.dumps({'works':len(works),'network_queries':budget.used,'alignments':len(aligns)},ensure_ascii=False))

def runall():
    if (RESULT/'environment.json').exists():
        raise SystemExit('Frozen results already exist. Use replay.ps1 or set SIXVOLUMES_RESULTS to a new relative directory.')
    dump(RESULT/'environment.json',{'python':sys.version,'platform':sys.platform,'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'protocol_sha256':digest((ROOT/'protocol.json').read_bytes()),'run_script_sha256':digest(Path(__file__).read_bytes()),'dataset_sha256':digest((ROOT/'data/documents.json').read_bytes()),'timestamp_unix':time.time()})
    make_pii()
    for method in METHODS:subprocess.run([sys.executable,__file__,'chunk-worker',method],check=True)
    for method in ['helan','presidio_zh_rules','helan_same_normalization']:subprocess.run([sys.executable,__file__,'pii-worker',method],check=True)
    sift();gewita();rag()
    modelfiles=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in (ROOT/'models').rglob('*') if p.is_file()]
    dump(RESULT/'model_manifest.json',{'model':'BAAI/bge-small-zh-v1.5','source':'https://huggingface.co/Qdrant/bge-small-zh-v1.5','license':'MIT per model/fastembed metadata','files':modelfiles})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['all','chunk-worker','pii-worker','rag','siftan','gewita']);parser.add_argument('method',nargs='?');args=parser.parse_args()
    if args.mode=='all':runall()
    elif args.mode=='chunk-worker':chunk_worker(args.method)
    elif args.mode=='pii-worker':pii_worker(args.method)
    elif args.mode=='rag':rag()
    elif args.mode=='siftan':sift()
    else:gewita()
