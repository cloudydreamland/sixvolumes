"""Collect exact installed license notices without making them runtime deps."""
import hashlib
import importlib.metadata as md
import json
from pathlib import Path
import shutil
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

licenses = {"colorama": "BSD-3-Clause", "tiktoken": "MIT"}
purposes = {"pytest": "工程回归测试", "jieba": "显式evaluation分词", "tiktoken": "可选精确token计数测试"}
packages = []
for dist in sorted(md.distributions(path=[str(ROOT / ".evaluation-deps")]), key=lambda d: d.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    key = name.lower()
    version = dist.version
    expression = licenses.get(key) or dist.metadata.get("License-Expression") or dist.metadata.get("License")
    assert expression and len(expression) < 100, (name, expression)
    retained = []
    notice_dir = ROOT / "third_party" / "licenses" / (key + "-" + version)
    notice_dir.mkdir(parents=True, exist_ok=True)
    for file in dist.files or []:
        if not any(tag in Path(str(file)).name.upper() for tag in ("LICENSE", "COPYING", "NOTICE")):
            continue
        original = Path(dist.locate_file(file))
        if not original.is_file():
            continue
        target = notice_dir / original.name
        shutil.copyfile(original, target)
        retained.append(dict(original_installed_path=original.relative_to(ROOT).as_posix(),
                             retained_path=target.relative_to(ROOT).as_posix(), sha256=sha(target)))
    if key == "jieba" and not retained:
        # The PyPI wheel/sdist omits the notice; retain the matching upstream tag.
        source = "https://raw.githubusercontent.com/fxsjy/jieba/v0.42.1/LICENSE"
        target = notice_dir / "LICENSE"
        if not target.exists():
            target.write_bytes(urllib.request.urlopen(source, timeout=30).read())
        assert "Permission is hereby granted" in target.read_text(encoding="utf-8")
        retained.append(dict(source=source, retained_path=target.relative_to(ROOT).as_posix(), sha256=sha(target)))
    assert retained, name
    packages.append(dict(name=name, version=version, license=expression,
                         source=f"https://pypi.org/project/{name}/{version}/",
                         purpose=purposes.get(key, "评测/测试工具的传递依赖"),
                         modifications="未修改发行包；jieba wheel由同版本源包本地构建",
                         obligations="分发保留原版权、许可与NOTICE；具体条件以所附全文为准", notices=retained))
save(ROOT / "DEPENDENCIES.json", dict(scope="evaluation dependencies, not core runtime", packages=packages))
provenance = json.loads((ROOT / "UPSTREAM_PROVENANCE.json").read_text(encoding="utf-8"))
rows = []
for record in provenance["repositories"]:
    pkg = record["package"]
    metadata = tomllib.loads((ROOT / "vendor" / pkg / "pyproject.toml").read_text(encoding="utf-8"))
    rows.append(dict(package=pkg, declared_version=metadata["project"]["version"], repository=record["repository"],
                     ref=record["ref"], retrieved_date=record["retrieved_date"],
                     upstream_archive_sha256=record["upstream_archive_sha256"],
                     license=record["license"], license_path=record["license_path"],
                     purpose={"helan":"中文脱敏与原文偏移", "worddael":"结构分块", "gewita":"引用格式与引语对齐", "siftan":"可选污染筛查", "tellan":"可选token对账与链一致性", "sothstan":"可选模型身份统计证据"}[pkg],
                     modifications="见LOCAL_PATCHES.md及逐文件LOCAL_CHANGES.json",
                     obligations="MIT：保留版权和许可全文；当前本地修复不冒称上游新版本"))
save(ROOT / "CORE_RESOURCES.json", dict(integration_version="0.2.0", snapshot_note="Declared upstream version plus exact archive SHA-256; no unverified commit SHA or release identity claimed", resources=rows))
lines = ["# 六库本版来源清单", "", "集成发行版0.2.0。六个上游pyproject均声明0.1.0；本地补丁另列，不能把main归档当成已发布新版本。来源于2026-10-23下载的main，归档SHA-256固定来源内容。", "", "| 包 | 上游声明版本 | 来源 | 许可/用途 |", "|---|---|---|---|"]
for row in rows:
    lines.append(f'| {row["package"]} | {row["declared_version"]} | [{row["repository"].split("/")[-1]}]({row["repository"]}) | MIT / {row["purpose"]} |')
lines += ["", "逐库完整归档哈希、用途、原LICENSE路径和义务见根目录CORE_RESOURCES.json；原始逐文件哈希见UPSTREAM_PROVENANCE.json；当前改动见LOCAL_CHANGES.json。六份原MIT许可随源码和wheel保留。", "", "测试/评测14个依赖的版本、来源、SPDX表达式、用途、修改说明、义务和原许可文件SHA-256见DEPENDENCIES.json，许可全文保存在third_party/licenses。colorama 0.4.6经安装发行包LICENSE.txt核实为BSD-3-Clause；tiktoken字段归一为MIT，原全文单独保留。jieba发行包未附LICENSE，补保留其对应v0.42.1源码标签原许可。"]
(ROOT / "docs/CORE_RESOURCES.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
print("Retained licenses:",len(packages),"dependencies;",len(rows),"core packages")
