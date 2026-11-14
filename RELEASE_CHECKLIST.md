# 发版检查单（RELEASE_CHECKLIST）

> 每次发布前逐项打勾；任何一项不通过则不发布。本检查单以工程实际脚本与命令为准（`scripts/verify_all.py`、`scripts/package_release.py`、`scripts/release_smoke.py`），执行环境需 Python 3.10+。

## 0. 版本号与变更内容确认

- [ ] 确认本版内容已全部合入 main；`CHANGELOG.md` 的 [未发布] 节内容完整、无未登记的合入改动。
- [ ] 将 [未发布] 节改为新版本号 + 实际发布日期；版本号遵循语义化版本（新增实体类型等功能取次版本号，纯修复取修订号）。
- [ ] 三处版本号一致：`pyproject.toml` 的 `version`、`src/sixvolumes/__init__.py` 的 `__version__`、`CHANGELOG.md` 新版本节标题。
- [ ] `scripts/package_release.py` 中离线 ZIP 命名（`sixvolumes-<version>-offline-source.zip`）与 wheelhouse glob 模式已随版本号更新（当前脚本内为 `0.2.0` 硬编码，发新版前必须同步）。

## 1. 测试全绿

- [ ] `python -m pip install ".[test]"` 后 `python scripts/verify_all.py --profile core --run-label release-<版本号>-<日期>`，退出码 0（core 进程显式屏蔽 jieba/tiktoken，验证核心零依赖可用）。
- [ ] `python -m pip install ".[evaluation]"` 后 `python scripts/verify_all.py --profile evaluation --run-label release-<版本号>-<日期>`，退出码 0（需 jieba 0.42.1 / tiktoken）。
- [ ] 记录两 profile 的通过/skip 数并写入 CHANGELOG 新版本节（如 2026-11-14 口径：1,817 通过/0 失败，core 906 + evaluation 911；skip 如实报告不计作通过）；两次 profile 数字不相加冒充更大规模。
- [ ] GitHub Actions CI 8 配置全绿（ubuntu/windows × Python 3.10–3.13，`ci.yml`）。
- [ ] `scripts/release_smoke.py` 通过（发布冒烟检查）。
- [ ] 统一 CLI 端到端复核：`demo` 默认场景退出码 0（overall=partial）；`--scenario contaminated` 与 `--scenario bad-quote` 退出码 1；`--require-all` 退出码 3。

## 2. 哈希与证据清单重算

- [ ] 运行 `python scripts/package_release.py`（离线）：重算 `LOCAL_CHANGES.json`、刷新 `src/sixvolumes/data/` 打包镜像、重建 `wheelhouse/` 核心 wheel 与 `dist/` 离线源码 ZIP，生成 `dist/SHA256SUMS.json`。
- [ ] 打包前清理回滚辅助文件（`*.bak_YYYYMMDD` 等），确认不进入 `SOURCE_MANIFEST.json` 与发布包。
- [ ] `UPSTREAM_PROVENANCE.json` 六库归档 SHA-256 与 `vendor/` 实际文件一致；`vendor/*/LICENSE` 六份原许可在位（逐项核对 `license_path` 字段）。
- [ ] 断网复跑哈希一致：拦截全部网络后重跑 `python run.py demo -o outputs/<断网目录>`，两次 `evidence_sha256` 完全一致。
- [ ] `python run.py verify outputs/<demo目录>/report` 输出 `passed`（demo 产出的报告目录为 `<demo目录>/report`，内含 artifacts.json；audit 场景下 `-o` 即报告目录）。artifacts 逐文件 SHA-256 与 report.evidence_sha256 重算一致。

## 3. 许可文件齐备

- [ ] 根目录 `LICENSE`（MIT）为最新；版权行与贡献者主体正确。
- [ ] `vendor/<六库>/LICENSE` 六份在位且与 `UPSTREAM_PROVENANCE.json` 的 `license_path`/SHA-256 一致。
- [ ] `third_party/licenses/` 内 14 个评测依赖的许可全文与 NOTICE 在位；`DEPENDENCIES.json` 逐项（含 colorama 0.4.6 = BSD-3-Clause、tiktoken = MIT、jieba 补保留 v0.42.1 源码标签许可）无缺漏。
- [ ] wheel 内附六库许可文本（`sixvolumes/data/licenses`）；`MANIFEST.in` 的 `recursive-include vendor ... LICENSE` 生效。
- [ ] 新增依赖（如有）：已登记 `DEPENDENCIES.json`、许可全文入库、`requirements-evaluation.txt`/`requirements.lock.txt` 同步。

## 4. 文档一致性

- [ ] `README.md` 中的测试口径、安装命令、退出码表与本版行为一致；诚实边界（不做/未做/待条件）与 `docs/EVIDENCE_LIMITS.md`、`ROADMAP_维护计划.md` 无矛盾。
- [ ] `docs/VALIDATION.md` 追加本版验收记录（沿用"上表保留不覆盖、新增另起"的写法）。
- [ ] `CHANGELOG.md` 新版本节日期为真实发布日期；不写尚未发生的内容。

## 5. Tag 与 PyPI 发布步骤

- [ ] 在干净工作区（`git status` 无未预期改动）执行：

```powershell
# 1) 构建与自检
python scripts/package_release.py            # 离线构建 wheel + 源码 ZIP + SHA256SUMS.json
python -m pip install --no-index --find-links wheelhouse sixvolumes-trust-pipeline  # wheel 可离线安装
python -m sixvolumes demo -o outputs/release-smoke && python run.py verify outputs/release-smoke/report
python -m twine check wheelhouse/sixvolumes_trust_pipeline-<版本>-*.whl

# 2) 打 tag
git tag -a v<版本号> -m "sixvolumes-trust-pipeline v<版本号>"
git push origin v<版本号>

# 3) 上传 PyPI（确认 CHANGELOG 日期与 tag 一致后再执行）
python -m twine upload wheelhouse/sixvolumes_trust_pipeline-<版本>-*.whl
```

- [ ] 上传前最后确认：PyPI 项目页 `sixvolumes-trust-pipeline` 当前版本列表与本版不冲突（当前已发布 0.2.0，2026-10-26 上传）。

## 6. 发布后验证与公告

- [ ] 全新环境（或干净虚拟环境）`python -m pip install sixvolumes-trust-pipeline`，`python -m sixvolumes demo -o outputs/installed-demo` 成功，`report.html` 自包含打开正常。
- [ ] PyPI 页面元数据正确（MIT 许可徽章、Python 3.10+、README 渲染）。
- [ ] GitHub Release：以 tag 发布，附 `dist/SHA256SUMS.json` 与离线 ZIP 哈希说明。
- [ ] 在 ROADMAP 第七节"进度回顾"追加本版记录；如有独立试用者等待的修复（如 Issue #1 修复承诺），在对应 issue 回帖公告并邀请复测。
- [ ] 若本版包含安全相关修复，在 CHANGELOG 中显式标注。

## 附：不发布条件（触发任意一条即推迟）

1. 任一 profile 测试存在失败（skip 不算失败但需如实报告）。
2. CI 任一配置失败。
3. 哈希清单无法重算一致，或断网复跑 `evidence_sha256` 不一致。
4. 许可文件缺失或与登记不符。
5. 冻结评测集被迫改动才能通过测试（应先修复改动本身）。
