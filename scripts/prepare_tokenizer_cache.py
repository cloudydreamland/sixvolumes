"""Explicit network step before evaluation; never invoked by the core pipeline."""
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cache=root/"outputs"/"tokenizer-cache"
cache.mkdir(parents=True,exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"]=str(cache)
import tiktoken
for name in ("cl100k_base","o200k_base"):
    tokenizer=tiktoken.get_encoding(name)
    print(name,"cached",len(tokenizer.encode("中文缓存测试")))
print("Set TIKTOKEN_CACHE_DIR="+str(cache)+" for fully offline evaluation runs.")
