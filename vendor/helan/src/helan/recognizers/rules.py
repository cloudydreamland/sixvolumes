"""格式规则类 recognizer：邮箱 / IP / URL / 座机 / 车牌 / 护照 / 本地文件路径。"""

from __future__ import annotations

import re

from ..data import LANDLINE_AREA_CODES, PLATE_PROVINCES
from ..types import (
    EMAIL,
    FILE_PATH,
    IP_ADDRESS,
    LANDLINE,
    LICENSE_PLATE,
    PASSPORT,
    URL,
    Entity,
)
from .base import guarded_pattern, make

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

_IPV4_RE = guarded_pattern(
    r"(?:\d{1,3}\.){3}\d{1,3}", left="0-9.", right="0-9"
)

# 512 上限:正常 URL 不受影响,同时约束实体最大长度(流式 overlap 的前提)
_URL_RE = re.compile(r"https?://[^\s<>\"'，。；！？、]{1,512}")

_LANDLINE_RE = guarded_pattern(r"0\d{2,3}-?[2-9]\d{6,7}")

_PLATE_RE = re.compile(
    rf"[{PLATE_PROVINCES}][A-HJ-NP-Z][·•]?(?:[A-HJ-NP-Z0-9]{{5,6}})"
)

_PASSPORT_RE = guarded_pattern(r"[EGDSPh]\d{8}", left="0-9A-Za-z", right="0-9A-Za-z")

_TRAILING_PUNCT = "。，,;；!！?？、）)】》\"'"


def recognize_email(text: str) -> list[Entity]:
    out = []
    for m in _EMAIL_RE.finditer(text):
        local = m.group(0).split("@")[0]
        if not local or local.startswith(".") or local.endswith("."):
            continue
        out.append(make(EMAIL, m, 0.9, "rule"))
    return out


def _ipv4_octets_ok(value: str) -> bool:
    return all(0 <= int(o) <= 255 for o in value.split("."))


def recognize_ip(text: str) -> list[Entity]:
    out = []
    for m in _IPV4_RE.finditer(text):
        value = m.group(0)
        if _ipv4_octets_ok(value):
            out.append(make(IP_ADDRESS, m, 0.9, "rule"))
    return out


def recognize_url(text: str) -> list[Entity]:
    out = []
    for m in _URL_RE.finditer(text):
        value = m.group(0)
        trimmed = value.rstrip(_TRAILING_PUNCT)
        out.append(make(URL, m, 0.9, "rule", trimmed_len=len(trimmed)))
    return out


def recognize_landline(text: str) -> list[Entity]:
    """区号有 2/3 位两种长度，正则无法决定切分；按区号表逐一尝试。"""
    out = []
    for m in _LANDLINE_RE.finditer(text):
        digits = m.group(0).replace("-", "")
        for k in (2, 3):
            if digits[1 : 1 + k] in LANDLINE_AREA_CODES:
                rest = digits[1 + k :]
                if 7 <= len(rest) <= 8:
                    out.append(make(LANDLINE, m, 0.85, "rule", area=digits[: 1 + k]))
                    break
    return out


def recognize_plate(text: str) -> list[Entity]:
    return [make(LICENSE_PLATE, m, 0.85, "rule") for m in _PLATE_RE.finditer(text)]


def recognize_passport(text: str) -> list[Entity]:
    return [make(PASSPORT, m, 0.85, "rule") for m in _PASSPORT_RE.finditer(text)]


# ---------- 本地文件路径（来源：使用者实测反馈漏检样例 C:\Users\name\file.txt） ----------
#
# 设计口径（诚实边界）：
# - 路径组件不含换行/制表、分隔符与 Windows 非法字符，可含空格与中文
#   （C:\Program Files (x86)\app\run.exe、D:\资料\合同.docx）。
# - 末段必须带 ASCII 扩展名，或以分隔符结尾（目录形式）；纯中文无扩展名的
#   末段（D:\资料\合同）不命中，避免把普通中文词误报成路径。
# - 盘符/UNC/Unix 三种形态；Unix 形态要求末段带扩展名，避免“甲/乙/丙”
#   这类顿号式斜杠并列误报。
# - 左侧守卫用 ASCII 词字符类：排除盘符前紧跟字母数字、URL scheme（如
#   https:// 内部）、更长反斜杠串；URL 实体优先级更高，URL 内部路径段
#   不重复切出。识别器内部去掉互相包含的重复命中。
_PATH_COMP_CHARS = r"[^\t\n\r\f\v\\/\"'<>|:：，。；！？、]"
_PATH_COMP = rf"{_PATH_COMP_CHARS}{{1,60}}"
_PATH_COMP_EXT = rf"{_PATH_COMP_CHARS}{{1,100}}\.[A-Za-z0-9]{{1,12}}"

_WIN_PATH_FILE_RE = guarded_pattern(
    rf"[A-Za-z]:[\\/](?:{_PATH_COMP}[\\/])*{_PATH_COMP_EXT}", left="0-9A-Za-z"
)
_WIN_PATH_DIR_RE = guarded_pattern(
    rf"[A-Za-z]:[\\/](?:{_PATH_COMP}[\\/])+", left="0-9A-Za-z"
)
_UNC_HOST = rf"\\\\[\w.\-]{{1,60}}[\\/]"
_UNC_PATH_RE = (
    guarded_pattern(rf"{_UNC_HOST}(?:{_PATH_COMP}[\\/])*{_PATH_COMP_EXT}", left=r"\\"),
    guarded_pattern(rf"{_UNC_HOST}(?:{_PATH_COMP}[\\/])+", left=r"\\"),
)
_UNIX_PATH_RE = guarded_pattern(
    rf"/(?:{_PATH_COMP}[\\/])*{_PATH_COMP_EXT}", left=r"0-9A-Za-z@\\/-"
)


def recognize_file_path(text: str) -> list[Entity]:
    raw = []
    for pattern in (_WIN_PATH_FILE_RE, _WIN_PATH_DIR_RE, *_UNC_PATH_RE, _UNIX_PATH_RE):
        raw.extend(m.span() for m in pattern.finditer(text))
    # 按 (start 升序, end 降序) 排序后丢弃被更长相邻命中包含的重复段
    ordered = sorted(set(raw), key=lambda s: (s[0], -s[1]))
    kept: list[tuple[int, int]] = []
    for start, end in ordered:
        if any(k_start <= start and end <= k_end for k_start, k_end in kept):
            continue
        kept.append((start, end))
    return [
        Entity(type=FILE_PATH, start=start, end=end, text=text[start:end],
               score=0.9, source="rule", meta={"cue": "local_path"})
        for start, end in kept
    ]


# 类型 -> recognizer 注册表（rules 组）
RULE_RECOGNIZERS = {
    EMAIL: recognize_email,
    IP_ADDRESS: recognize_ip,
    URL: recognize_url,
    LANDLINE: recognize_landline,
    LICENSE_PLATE: recognize_plate,
    PASSPORT: recognize_passport,
    FILE_PATH: recognize_file_path,
}
