"""Map transformed text back to the original without publishing raw entities."""
import hashlib
from helan import Vault
from .pii import recognize_identifiers


def redact_with_lineage(text: str, profile="normalized"):
    entities = recognize_identifiers(text, profile)
    prefix = "sv_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] + "_"
    while "<" + prefix in text:
        prefix += "x"
    vault = Vault(prefix=prefix)
    parts, segments, evidence = [], [], []
    source_pos = output_pos = 0
    for e in entities:
        if not (source_pos <= e.start < e.end <= len(text)) or text[e.start:e.end] != e.text:
            raise ValueError("Helan returned an overlapping or invalid entity span")
        if e.start > source_pos:
            part = text[source_pos:e.start]
            parts.append(part)
            segments.append(dict(kind="copy", masked_start=output_pos, masked_end=output_pos+len(part), source_start=source_pos, source_end=e.start))
            output_pos += len(part)
        token = vault.place(e.type, e.text)
        parts.append(token)
        segments.append(dict(kind="redaction", masked_start=output_pos, masked_end=output_pos+len(token), source_start=e.start, source_end=e.end, entity_type=e.type))
        evidence.append(dict(type=e.type, start=e.start, end=e.end, score=e.score))
        output_pos += len(token)
        source_pos = e.end
    if source_pos < len(text):
        part = text[source_pos:]
        parts.append(part)
        segments.append(dict(kind="copy", masked_start=output_pos, masked_end=output_pos+len(part), source_start=source_pos, source_end=len(text)))
    masked = "".join(parts)
    if vault.restore(masked) != text:
        raise ValueError("Vault roundtrip invariant failed")
    return masked, vault, segments, evidence


def source_spans(start, end, segments):
    """Copy spans map exactly; an intersected replacement maps to its entire source entity."""
    result = []
    for s in segments:
        a, b = max(start, s["masked_start"]), min(end, s["masked_end"])
        if a >= b:
            continue
        if s["kind"] == "copy":
            left = s["source_start"] + a - s["masked_start"]
            right = left + b - a
        else:
            left, right = s["source_start"], s["source_end"]
        result.append(dict(kind=s["kind"], source_start=left, source_end=right, masked_start=a, masked_end=b))
    return result
