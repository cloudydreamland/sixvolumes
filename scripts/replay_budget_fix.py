"""Read-only replay of seen data; never updates frozen benchmark results."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "vendor/worddael/src"))
from worddael import RecursiveChunker

evaluation = Path(sys.argv[1]).resolve()
data_path = evaluation / "data/documents.json"
frozen_path = evaluation / "results/worddael_recursive_performance.json"
frozen_bytes = frozen_path.read_bytes()
documents = [d for d in json.loads(data_path.read_text(encoding="utf-8")) if d["split"] == "holdout"]
chunks = []
errors = uncovered = 0
for doc in documents:
    text = doc["text"]
    cs = RecursiveChunker(max_chars=256, overlap_chars=0).chunk(text)
    cursor = 0
    for c in cs:
        errors += int(c.text != text[c.start:c.end])
        uncovered += max(0, c.start - cursor)
        cursor = c.end
    uncovered += len(text) - cursor
    chunks.extend(cs)
result = dict(note="Post-failure engineering replay on already seen data. Not new independent holdout evidence; no RAG-quality claim or threshold tuning.",
              command=[sys.executable, *sys.argv],
              frozen_source=str(frozen_path), frozen_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
              frozen_metrics=json.loads(frozen_bytes),
              data_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
              patched_metrics=dict(documents=len(documents), chunks=len(chunks), oversize_chunks=sum(len(c.text)>256 for c in chunks),
                                   max_chunk_chars=max(len(c.text) for c in chunks), offset_errors=errors, uncovered_chars=uncovered),
              source_sha256=hashlib.sha256((root / "vendor/worddael/src/worddael/chunkers.py").read_bytes()).hexdigest(),
              frozen_unchanged=frozen_path.read_bytes() == frozen_bytes)
target = root / "outputs/validation/budget-fix/seen-data-replay.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(result["patched_metrics"]))
assert result["frozen_unchanged"] and errors == uncovered == result["patched_metrics"]["oversize_chunks"] == 0
