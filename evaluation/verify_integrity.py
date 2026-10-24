from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
manifest=json.loads((root/'SHA256SUMS.json').read_text(encoding='utf-8'))
bad=[]
for item in manifest:
    p=root/item['path']
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:bad.append(item['path'])
print(json.dumps({'checked':len(manifest),'mismatches':bad},ensure_ascii=False))
sys.exit(bool(bad))
