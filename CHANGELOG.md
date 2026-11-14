# 更新日志（CHANGELOG）

本工程遵循语义化版本；所有条目只记录真实发生的内容，日期为实际完成/发布日期。

> **版本口径说明（核对日 2026-11-14）**
> - 集成发行版首次成套发布即 **0.2.0**（PyPI `sixvolumes-trust-pipeline`，2026-10-26 上传；GitHub 仓库 2026-10-24 创建）。本仓库**没有 0.1.x 的集成发行版发布记录**，不虚构该版本条目。
> - `0.1.0` 是六个上游 vendored 库各自声明的版本号（2026-10-23 main 下载快照，见 `docs/CORE_RESOURCES.md` 与 `UPSTREAM_PROVENANCE.json`），其自身演进见各上游仓库。
> - NegQuote 预研模块独立编版本（v0.1 → v0.1.1），不与集成发行版版本号混用。

## [0.2.1] - 2026-11-14

> 独立使用者反馈修复版。wheel 与离线源码包已构建并通过发布冒烟（隔离安装、七模块导入、demo overall=partial、产物校验、6 份核心许可齐全，退出码 0），随工程源码包 `dist/` 交付；PyPI 上传在仓库推送后按 `RELEASE_CHECKLIST.md` 执行。git 提交：fix(helan) 与 evidence 两个提交。

### 新增（Helan PII 规则修复，来源：三位独立使用者实测反馈 Issue #1/#2）

- **手机号 3-4-4 分组写法识别**：`138-1234-5678`、空格分隔、全角分隔均检出；去分隔符归一化后仍过号段表（`140-1234-5678` 仍拒检）。
- **微信号新增 `wxid_` 前缀形态**：无"微信号"关键词上下文也可检出；左守卫排除从长 token、路径内部切出。
- **地址允许内部空格/全角空格/制表符**：句读前尾随空白不并入地址实体；行界仍不得进入地址。
- **新增 `FILE_PATH` 实体类型**：Windows 盘符 / UNC / Unix 绝对路径三形态，末段须带 ASCII 扩展名或以分隔符结尾；默认算子 redact，优先级（28）低于 URL（30）避免 URL 内部切分。诚实边界：纯中文无扩展名末段（如 `D:\资料\合同`）不命中。
- **"高级工程师"误报修复**："高级"加入人名停用词并在称谓线索同口径启用，不再误判为人名；`张伟明工程师` 等真实称谓仍正常检出。

### 变更（行为核实，不改代码）

- **身份证 X 结尾**：经复核为合法拒检——校验位合法（ISO 7064 MOD 11-2）的 `X`/`x`/全角`Ｘ`/分组形态在修复前已全部检出；校验位不符的合成号按"宁缺勿滥"设计拒检。**校验门保持不放宽**，新增双向回归测试锁定该行为。

### 新增（测试）

- 新增 56 条回归测试先红后绿：helan 单元 31 条 + 产品级集成回归 25 条（`tests/test_pii_user_feedback.py`，含用户报告原始样例）。
- 修复前同套测试实测：integration 39 通过/11 失败、helan 识别器子集 34 通过/10 失败（留档于 `outputs/validation/pii-baseline-pre-fix/`）。
- 测试总口径由 1,691（2026-10-23）升级为 **1,817 通过/0 失败**（core 906 + evaluation 911，2026-11-14 全量重跑，`scripts/verify_all.py` 两 profile 退出码 0，run-label=`pii-fix-20261114-final`）。

### 变更（文档与清单）

- `LOCAL_PATCHES.md` 新增"Helan PII 规则修复（2026-11-14）"条目；`LOCAL_CHANGES.json` 按打包同口径重算。

## [0.2.0] - 2026-10-26（已发布）

### 新增

- 统一 CLI：`run.py demo / audit / verify` 与 `sixvolumes`、`python -m sixvolumes` 入口；核心零必需第三方依赖，不调用外部 API。
- 六个公开 MIT 工具库 vendored 集成（Helan=PII脱敏、Worddael=切块血缘、Gewita=引用核对、Siftan=污染筛查、Tellan=费用对账、Sothstan=端点审计，各 0.1.0 快照），统一四态判定（passed/failed/unavailable/error）与失败退出码（0/1/2/3）。
- 报告体系 `sixvolumes.evidence/v1`：`report.json`（`evidence_sha256` 证据摘要哈希）、自包含 `report.html`、`artifacts.json` 逐文件 SHA-256 清单与 `verify` 独立重算；断网复跑哈希一致。
- `--pii-profile native|normalized`：有界 NFKC/零宽/孤立分隔字符识别视图，维护逐字符原始偏移，禁止跨行拼接（由外部评测发现格式失效后新增的工程改进）。
- 离线工程：wheelhouse 离线安装、`scripts/install_offline.ps1`、`scripts/package_release.py`（离线构建 wheel + 源码清单 + 离线 ZIP）、`scripts/prepare_tokenizer_cache.py`、`scripts/verify_all.py`（core/evaluation 双 profile）。
- 治理清单：`UPSTREAM_PROVENANCE.json`（六库归档 SHA-256 与逐文件哈希）、`CORE_RESOURCES.json`、`DEPENDENCIES.json`、`SOURCE_MANIFEST.json`、`LOCAL_CHANGES.json`。
- CI：GitHub Actions 8 配置矩阵（ubuntu/windows × Python 3.10–3.13）。
- 集成验收记录（`docs/VALIDATION.md`）：core 843 通过/10 skip、evaluation 848 通过/5 skip、0 失败（2026-10-23 实跑；skip 如实计数）。

### 修复

- **Worddael 字符上限硬预算**（2026-10-24）：冻结外测发现 4 块为 257 字、超过 256 上限；现对长原子句先拆分、边界移动同时约束左右块、overlap 计入最终硬上限；无法兼顾标点时优先保留预算与完整精确偏移，不通过丢字规避超限。新增 6 条 Worddael 边界回归 + 1 条集成回归，预算断言收紧；复验命令 `python scripts/verify_all.py --profile core --components integration worddael --run-label budget-fix`。
- **Tellan 本地代理**：loopback/localhost 上游改用禁代理的 urllib opener（系统代理曾把闭端口错误改写为空 502）；外部上游仍尊重代理配置，含恶意/失效 proxy 环境回归。
- **Tellan 可选依赖**：未装 tiktoken 时真实 tokenizer 集成测试显式 skip；不支持模型族门禁用注入式 tokenizer，不隐式下载。
- **Worddael 评测配置固定**：ContextVar 固定 core/jieba 配置，默认 core 不调用可选分词器；上游 jieba 历史报告另存（`vendor/worddael/benchmarks/results.upstream-jieba.md`），跨配置数字不混用。
- **Siftan 公开 API** 补导出 `build_index`，与使用示例一致；算法不变。

### 预研

- **NegQuote 否定感知引语门控** v0.1（2026-10-24，215 个冻结合成探针）：最小否定编辑拦截 39/40、非否定探针 0 误触发；v0.1.1（2026-10-25，同集复测）：扩充 16 条"不+动词"线索后 **40/40**，无误触发；探针语料与门控逻辑零改动，逐条 diff 共 2 条。

### 文档

- README（含诚实边界与退出码）、`docs/EVIDENCE_LIMITS.md`、`docs/VALIDATION.md`、`docs/THIRD_PARTY.md`、`docs/CORE_RESOURCES.md`、`preresearch/negquote/REPORT.md`。

### 发布

- 2026-10-24：GitHub 仓库创建（github.com/cloudydreamland/sixvolumes）；发布 [Issue #1](https://github.com/cloudydreamland/sixvolumes/issues/1) 征集独立试用者；离线源码 ZIP 构建入 `dist/`。
- 2026-10-26：**PyPI 上传 `sixvolumes-trust-pipeline` 0.2.0**（零运行时依赖 wheel）。

## [同期外部记录（非本仓库版本）]

- 2026-10-26 / 10-27：三位独立试用者公开反馈（[Issue #2](https://github.com/cloudydreamland/sixvolumes/issues/2) 4.8/5；[Issue #1](https://github.com/cloudydreamland/sixvolumes/issues/1) 3.5/5 与 4/5，差评原样保留）。
- 2026-11-05：团队在 Issue #1 逐条复现反馈并归类回复（确认要修 / 设计取舍 / 已立案）。
- 2026-11-01：缺陷回馈闭环——团队 Issue presidio#2396（中文全角/零宽漏检）促成的维护者修复 PR [presidio#2397](https://github.com/microsoft/presidio/pull/2397) 合并进入上游主干。
- 2026-11-14：PII 定向修复与回归完成，随 v0.2.1 交付（见上节）。
