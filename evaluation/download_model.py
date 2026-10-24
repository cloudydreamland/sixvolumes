"""Download the disclosed MIT Chinese embedding model; no API credentials needed."""
from pathlib import Path
import os
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
from fastembed import TextEmbedding
ROOT=Path(__file__).resolve().parent
model=TextEmbedding('BAAI/bge-small-zh-v1.5',cache_dir=str(ROOT/'models'),threads=2)
print(next(model.embed(['中文模型加载验证'])).shape)
