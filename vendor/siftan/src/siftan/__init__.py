"""Siftan — 基准污染检测。

结果仅限于给定索引的字面重叠，不构成训练数据未污染的证明。

siftan 把基准语料变成可携带的 n-gram 指纹索引，对任意数据集/微调集筛查，
出具带索引哈希的"污染证明书"（contamination certificate）。
"""

from siftan._version import __version__
from siftan.check import ContaminationCertificate, screen
from siftan.index import ContaminationIndex, build_index
from siftan.ngrams import hamming_distance, ngrams, normalize, simhash64

__all__ = [
    "ContaminationCertificate",
    "ContaminationIndex",
    "build_index",
    "screen",
    "normalize",
    "ngrams",
    "simhash64",
    "hamming_distance",
    "__version__",
]
