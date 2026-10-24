"""Bounded Unicode adapter, added after diagnostics; not a new holdout result.

NFKC expands characters with an index map. Only the identifier recognition view
removes zero-width characters and isolated horizontal spaces within ASCII runs;
line/paragraph boundaries are never removed. Returned offsets refer to ORIGINAL
text. Native entity recognition remains in the candidate set.
"""
from dataclasses import replace
import re
import unicodedata
from helan import recognize
from helan.resolver import resolve

TARGETS = ("ID_CARD", "BANK_CARD", "PHONE", "EMAIL", "USCC")
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}
ASCII_ID = re.compile(r"[A-Za-z0-9@._%+\-]")


def normalized_view(text):
    chars, indexes = [], []
    for i, c in enumerate(text):
        if c in ZERO_WIDTH:
            continue
        for normalized in unicodedata.normalize("NFKC", c):
            chars.append(normalized)
            indexes.append(i)
    kept, mapped = [], []
    for i, c in enumerate(chars):
        if c in {" ", "\t"} and 0 < i < len(chars)-1:
            if ASCII_ID.fullmatch(chars[i-1]) and ASCII_ID.fullmatch(chars[i+1]):
                continue
        kept.append(c);mapped.append(indexes[i])
    return "".join(kept), mapped


def recognize_identifiers(text, profile="normalized"):
    native = recognize(text)
    if profile == "native":
        return native
    if profile != "normalized":
        raise ValueError("PII profile must be native or normalized")
    view, positions = normalized_view(text)
    candidates = list(native)
    for e in recognize(view, types=list(TARGETS)):
        start, end = positions[e.start], positions[e.end-1]+1
        original = text[start:end]
        if "\n" in original or "\r" in original or re.search(r"[ \t]{2,}", original):
            continue
        if len(original) > 2 * len(e.text) + 4:
            continue
        candidates.append(replace(e, start=start, end=end, text=original,
                                  meta={**e.meta, "normalization": "bounded-nfkc-offset-map-v1"}))
    return resolve(candidates)
