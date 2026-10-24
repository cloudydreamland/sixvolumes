"""Test-only simulation of the supported core installation without extras."""
import importlib.abc
import os
import sys

if os.environ.get("SIXVOLUMES_CORE_ONLY") == "1":
    class NoOptional(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"jieba", "tiktoken"}:
                raise ModuleNotFoundError("Optional dependency intentionally absent in core test profile", name=fullname)
    sys.meta_path.insert(0, NoOptional())
