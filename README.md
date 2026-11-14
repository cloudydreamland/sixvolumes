# 六卷书 · 中文知识库证据管线（sixvolumes）

> 把中文知识库送进一条**离线、可复核、不伪造证据**的处理管线：得到脱敏文本、可追溯切块、引用核对、可选污染筛查，以及一份任何人都能打开检查的 JSON + HTML 证据报告。

[![CI](https://github.com/cloudydreamland/sixvolumes/actions/workflows/ci.yml/badge.svg)](https://github.com/cloudydreamland/sixvolumes/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sixvolumes-trust-pipeline)](https://pypi.org/project/sixvolumes-trust-pipeline/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

六个公开 MIT 工具库的可安装集成发行版。核心无需第三方运行依赖，也不调用外部 API。当前质量口径：**1,817 项自动化测试 0 失败**（core 906 + evaluation 911，2026-11-14 全量重跑；另有 15 条环境相关 skip 如实计数，skip 不计作通过）。

## 20 秒理解

| | 内容 |
|---|---|
| **问题** | 把中文语料交给 LLM/RAG 前，"跑通了"不等于"可信"：脱敏漏没漏、切块偏移对不对、引用是不是真的、有没有基准污染——大多数工具给不出逐文档可复核的证据 |
| **做法** | 把六个 MIT 工具（Helan=PII脱敏、Worddael=切块血缘、Gewita=引用核对、Siftan=污染筛查、Tellan=费用对账、Sothstan=端点审计）接入统一 CLI，每一步输出哈希、字符偏移与四态判定；没证据的检查显示 `unavailable`，绝不冒充通过 |
| **产物** | `report.json`（机器可读，含 `evidence_sha256` 证据摘要哈希）+ 自包含 `report.html`（不加载外部资源）+ `artifacts.json`（逐文件 SHA-256 清单，可用 `verify` 子命令独立重算） |

## 快速开始（5 分钟版）

需要 Python 3.10+。全程不需要联网调用任何大模型 API。

```powershell
# 方式一：从 PyPI 安装（零运行时依赖）
python -m pip install sixvolumes-trust-pipeline
python -m sixvolumes demo -o outputs/installed-demo

# 方式二：源码直接跑（无需安装、无需联网）
git clone https://github.com/cloudydreamland/sixvolumes
cd sixvolumes
python run.py demo -o outputs/demo-clean
```

打开 `outputs/demo-clean/report/report.html`。默认结果应为 `partial`：Helan、Worddael、Gewita、Siftan 四卷已执行；没有真实调用账本和官方模型基线时，Tellan、Sothstan 显示 `unavailable`——**这不是六卷全部通过，也不是故障**。演示数据为原创合成样例，不是真实客户案例或独立效果验证。

再跑一个"故意搞坏"的场景，观察退出码与报告变化：

```powershell
python run.py demo -o outputs/demo-negative --scenario contaminated   # 应返回退出码 1：发现了污染
python run.py demo -o outputs/demo-bad-quote --scenario bad-quote     # 应返回退出码 1：发现无来源引语
python run.py demo -o outputs/demo-strict --require-all               # 严格模式因缺少两卷证据返回 3
```

程序没有为了演示而伪造真实 API 结果。

## 快速开始（15 分钟完整复现版）

来自《独立用户复现指南》，与三位独立试用者的实测路径一致（约 15 分钟）：

1. 解压源码包或 `git clone`，进入目录，运行 `python run.py demo -o outputs/my-first-demo`。
2. 打开 `report.html`：看哪几卷 `passed`、哪几卷 `unavailable`（默认 4 卷执行、2 卷因未接真实账本/端点而 unavailable——设计行为）；点开任一"脱敏/切块/引用"条目，看原文偏移与替换对照。
3. 跑 `python run.py demo -o outputs/my-negative --scenario contaminated`，确认退出码 1。
4. （可选）把你手头一段中文 `.md`/`.txt` 放进文件夹：`python run.py audit 你的文件夹 -o outputs/my-report`，再 `python run.py verify outputs/my-report`。
5. 进阶核验：**拦截全部网络后重跑 demo，比对两次 `evidence_sha256` 是否一致**（一位试用者实测：0 次外连、两次哈希完全一致）。
6. 欢迎按 [Issue #1](https://github.com/cloudydreamland/sixvolumes/issues/1) 的反馈表公开提交试用反馈，差评同样原样保留。

## 处理自己的知识库

```powershell
python run.py audit examples/knowledge -o outputs/my-report --sources examples/sources --quotes examples/quotes.json
python run.py verify outputs/my-report
```

`input` 为一个 `.txt` / `.md` 文件或目录，UTF-8 编码；空文件、无文本文件或不可解码文件会报错。暂不解析 PDF、Word、图片和 OCR。引用 JSON 格式：

```json
{"quotes":[{"id":"q1","source":"政策.txt","quote":"需要逐字核对的引语。"}]}
```

`source` 是来源目录内的相对路径。未给 `--sources` 时使用输入知识库；这只能核对词面和来源位置，不能证明知识本身真实。引用出版物存在性默认 `UNVERIFIED_OFFLINE`。

## 四态判定与退出码

六个卷统一为四种状态（另合成 `overall`：passed / partial / failed / error）：

| 状态 | 含义 | 典型情形 |
|---|---|---|
| `passed` | 已执行，且其**文档化范围内**的检查通过；不代表敏感信息召回率 100% 或内容真实 | 四卷正常执行且不变量通过 |
| `failed` | 已执行，且**发现了问题** | 字面污染命中、无来源引语、账本哈希链损坏、行为不一致 |
| `unavailable` | 证据未提供或无法判定，**不以零检测项冒充通过** | 未提供 `--ledger`、未配置官方模型基线、未给基准索引 |
| `error` | 输入或执行错误 | 不可解码输入、运行异常 |

| 退出码 | 含义 |
|---|---|
| 0 | 已执行且可判定的检查无失败；总状态仍可能是 partial |
| 1 | 检查发现问题，如字面污染、无来源引语、账本损坏、行为不一致 |
| 2 | 输入或执行错误，不能当作通过 |
| 3 | `--require-all` 下存在 unavailable |

## `unavailable` 是设计，不是缺陷

很多演示工具用 mock 数据伪造"6/6 全部通过"。六卷书反其道而行：**没有真实证据的卷如实标 `unavailable`，并支持严格退出码**。三位未参与开发的试用者对此的公开原话（[Issue #1](https://github.com/cloudydreamland/sixvolumes/issues/1)、[Issue #2](https://github.com/cloudydreamland/sixvolumes/issues/2)）：

> "非常诚实，是本工具最值得称赞的设计哲学与工程美德。……六卷书在没有真实 API 账单和没有配置官方模型端点及 --allow-live 授权时，如实标为 unavailable 并给出'部分完成（4/6）'，不伪造证据。" —— Charles236

> "unavailable 是诚实的，而且是我最认可的设计。我自己跑的时候 Gewita 和 Siftan 也是 unavailable，而不是偷偷'0/0 通过'。" —— meili-loli

> "诚实，刚开始有点困惑，看了文档后理解了。" —— Freya0821

## 六卷如何连起来

1. 读入原始字节并计算 SHA-256。原文仅保留在本机输入目录。
2. Helan 检测实体；集成层可用有界 Unicode 规范化补充格式变体识别（`--pii-profile normalized`，默认；`native` 为冻结原生配置）。用 Vault 占位符替换并实际验证还原闭环。默认不保存 Vault。
3. Worddael 对脱敏文本切块，验证 `chunk.text == masked[start:end]`，每块附转换段到原文字符范围的映射。偏移单位是 Unicode 字符，不是 UTF-8 字节。
4. Gewita 解析参考文献格式，并把显式提供的引语对齐到给定原始来源；规范化逐字命中也会单独标出 `exact_literal`。
5. 若提供 `--contamination-index benchmark.tsi`，Siftan 在**脱敏前原文**上筛查，避免隐私替换掩盖重叠。索引必须是真实使用者提供；CLEAN 只限于该索引的字面检测范围。
6. 若提供 `--ledger api.jsonl`，Tellan 校验哈希链并以明确的 heuristic 模式对账。若提供 `--sothstan-config model.json --allow-live`，Sothstan 使用非 demo 官方基线做有限预算行为审计。

机器报告保留输入哈希、索引哈希、来源和限定语。HTML 完全自包含，不加载外部字体或脚本。

## 诚实边界（不做 · 未做 · 待条件）

**不做（显式取舍）**

- 暂不解析 PDF、Word、图片和 OCR，只接受 UTF-8 `.txt`/`.md`。
- 集成版不自研密码算法；**Vault 是含原始敏感值的明文映射，不是加密或密钥**。如确需还原，使用 `--vault-dir` 指向与报告完全分离的受保护目录，不要对外分享。
- 哈希链和文件哈希只检查内容一致性，不是签名、身份认证或原始数据真实性证明。
- Tellan 内置价格为历史快照，未重新逐项核实，费用数字不可用作财务结算。
- Sothstan 的 AUTHENTIC 只表示与所给基线行为一致，不能排除精巧转发。
- 13-gram 污染检测是字面重叠检测，未命中不证明训练未污染；引用出版物存在性默认 `UNVERIFIED_OFFLINE`。
- 规则脱敏可能漏检或误报，`passed` 仅表示已执行转换与不变量校验，不保证合规结果。

**未做（已立案，列入路线图）**

- 句中人名识别（依赖 NER）——来自试用者反馈"句子中间的人名认不出"，已立案，见 [ROADMAP_维护计划.md](ROADMAP_维护计划.md)。
- 独立保留集上的 PII 修复后验证——2026-11-14 的 PII 规则修复是看到反馈失效后的工程修复与诊断，**不能把同一评测集上的修复后结果冒称全新独立验证**；必须用新的独立保留集再次验证。局限和测试见 `docs/EVIDENCE_LIMITS.md`。
- 报告可读性四项文案改进与 `selfcheck` 对抗格式自检子命令——来自反馈，逐项见路线图。

**待条件（证据到位即自动启用）**

- Tellan 费用对账：需要真实调用账本（`--ledger api.jsonl`）。
- Sothstan 端点审计：需要目标和一个可混淆近邻的非 demo 官方基线（`--sothstan-config model.json --allow-live`）。
- NegQuote 转正 v1.0：需要不少于 300 对真实引语与未参与开发者的人工复核。

## 预研：NegQuote 否定感知引语门控

外部公开数据评测发现：引语中加入"并非/没有"类否定词后，Gewita 仍可能给出 NEAR（近逐字）裁决——引语说了反话，词面却近乎逐字命中。基于"LLM 否定理解不可靠"的文献共识，`preresearch/negquote/` 实现了**规则化降级**（不假装语义理解）：引语含否定线索而对齐片段不含时，支持性裁决降级为 `UNSUPPORTED_PENDING_REVIEW` 交人工复核。

- v0.1（215 个冻结合成探针）：最小否定编辑拦截 39/40，135 个非否定探针 0 误触发；"不+动词"线索缺口如实报告。
- v0.1.1（同集复测）：按预告扩充 16 条"不+动词"线索后，最小否定编辑拦截 **40/40**，无误触发；探针语料与门控逻辑零改动，逐条 diff 共 2 条（1 条目标类真阳性 + 1 条语义反转的正确触发）。
- 边界：合成语料上的行为描述；镜像方向未覆盖；生产可用性需 ≥300 对真实引语 + 未参与开发者的人工复核（v1.0 计划）。详见 `preresearch/negquote/REPORT.md` 与两份结果 JSON。

## 真正的外部证据接入

`docs/sothstan-config.example.json` 是配置模板，密钥仅通过环境变量读取，不放入配置或报告。未设置 `--allow-live` 不联网，未配置不通过。默认预算最多 24 个请求、4000 个提示 token、单请求 10 秒；实际输出 token 及服务侧计费还需自行核对。

```powershell
python -m sothstan.cli collect https://OFFICIAL-ENDPOINT/v1 --model MODEL --family FAMILY --out baselines/MODEL.json --api-key-env MODEL_API_KEY
sixvolumes audit knowledge -o report --sothstan-config model.json --allow-live
```

请在隔离环境使用本发行版，它打包了六库相同顶层模块名，避免与单独安装的上游六包同时混装。

## 安装、离线使用与验证

发布于 PyPI（`pip install sixvolumes-trust-pipeline`），源码的 `run.py` 也可直接离线运行；wheel 无运行依赖。已有 Python 3.10+ 时，源码的 `run.py` 可直接离线运行。离线安装：

```powershell
python -m pip install --no-index --find-links wheelhouse sixvolumes-trust-pipeline
python -m sixvolumes demo -o outputs/installed-demo
```

`scripts/install_offline.ps1` 可创建隔离虚拟环境并从本地 wheelhouse 安装。不能联网或没有 pip 时直接运行源码入口。

```powershell
python -m pip install ".[test]"
python scripts/verify_all.py --profile core
python -m pip install ".[evaluation]"
python scripts/verify_all.py --profile evaluation
```

core 测试进程显式屏蔽 jieba/tiktoken，确保核心确实可在两者缺失时工作；evaluation 明确要求两者存在，使用 `requirements-evaluation.txt` 固定版本。词表缓存下载单独由 `scripts/prepare_tokenizer_cache.py` 完成，普通管线不隐式下载模型。

离线 ZIP 还提供 Windows CPython3.12 对应的 `wheelhouse/evaluation` 与 `outputs/tokenizer-cache`：`pip install --no-index --find-links wheelhouse/evaluation -r requirements-evaluation.txt` 后将 `TIKTOKEN_CACHE_DIR` 指向该缓存，可离线重跑 evaluation。其他 Python/系统需要自行准备相应 wheels。4 条 LangChain 适配器测试及 1 条外部小说测试未在本次环境启用；详见 `docs/VALIDATION.md`，跳过没有计作通过。

Worddael 内置报告默认固定 `core` 分词配置；`python -m worddael.eval.report --profile jieba` 是另一独立配置。上游原数字保存在 `vendor/worddael/benchmarks/results.upstream-jieba.md`，不与新版 core 数字混用。

`python scripts/package_release.py` 在已具备 setuptools/wheel 的环境离线构建 wheel，并生成源码清单和离线 ZIP。`UPSTREAM_PROVENANCE.json` 固定六个下载归档的 SHA-256 与原始文件哈希；`LOCAL_PATCHES.md` 说明集成修复。上游所有 LICENSE 均保留，wheel 内附六库许可文本。

2026-10-24 修复 Worddael 字符上限：`max_chars` 现在包含 overlap 和标点调整，不能以吸收标点为由超出上限；无法兼顾时优先保留完整覆盖和预算。冻结外测原始 4 个 257 字块仍保留，修复后已见数据只算工程回归，记录与局部复验计数见 `docs/VALIDATION.md`。六库版本/来源清单见 `docs/CORE_RESOURCES.md`；14 个评测依赖的原许可与 NOTICE 随离线包保存。

## 开源回馈：向上游的 17 项 PR 与缺陷修复闭环

本作品的技术栈（文档 AI、嵌入检索、隐私合规）与上游社区同域，回馈不是宣传素材而是持续协作记录（均附公开链接可查）：

| 结果 | 明细 |
|---|---|
| 团队 PR 已合并（7 项） | docling#4482（10-04）、docling#4484（10-05）、docling#4483（10-06）、docling#4567（10-07）、sentence-transformers#4129（10-08）、mineru-vl-utils#146（10-09）、docling#4596（10-29） |
| 缺陷报告促维护者修复合并（1 项） | 团队 Issue [presidio#2396](https://github.com/microsoft/presidio/issues/2396)（中文全角/零宽漏检，480 例冻结评测集佐证）→ 维护者提交修复 PR [presidio#2397](https://github.com/microsoft/presidio/pull/2397)（"Fixes #2396"，opt-in 文本归一化：NFKC + 格式字符剔除、命中映射回原文偏移、默认行为不变）→ **2026-11-01 合并进入上游主干**，完成"缺陷发现 → 维护者修复 → 合并进主干"完整闭环 |
| 评审中（3 项） | docling-core#836、markitdown#2620、markitdown#2609 |
| Issue 侧 | presidio#2396、docling#4481、docling#4595、PyEPO#68 已关闭；docling-core#835/#837 开放；presidio#2421（\b 词边界把汉字当词字符）开放 |

累计向上游提交 **17 项 PR**（docling×6、sentence-transformers×3、mineru-vl-utils×3、faster-whisper×2、markitdown×2、docling-core×1）与 **6 项上游 Issue**，每一条都有下文。

## 独立使用者的公开反馈（含差评，原样保留）

三位未参与开发的试用者按 15 分钟复现指南独立完成安装与复现，反馈公开在 GitHub（团队承诺差评原样引用，不只挑好听的）：

| 反馈人（匿名） | 位置 | 总分 | 要点（含差评） |
|---|---|---|---|
| Charles236 | [Issue #2](https://github.com/cloudydreamland/sixvolumes/issues/2) | 4.8/5 | "unavailable 是本工具最值得称赞的设计哲学"；建议卡片副标题补充"非运行故障"说明；血缘折叠项 JSON 不够直观 |
| Freya0821 | [Issue #1](https://github.com/cloudydreamland/sixvolumes/issues/1) | 3.5/5（证据链设计 5 分，**脱敏效果 2 分**） | 身份证/分隔符手机号漏检、人名识别依赖"姓名："前缀、"高级工程师"误报、max_chars 偏小 |
| meili-loli | [Issue #1](https://github.com/cloudydreamland/sixvolumes/issues/1) | 4/5 | 断网复跑哈希一致、自行复算 67 块偏移不变量全过；**四条脱敏漏检差评**（横杠手机号、含空格地址、wxid_ 微信号、本地路径）与四条报告文案建议 |

团队于 2026-11-05 在 Issue #1 逐条复现并归类回复；2026-11-14 完成 PII 定向修复：反馈的 6 项脱敏缺陷中 **5 项代码修复 + 1 项行为核实**，56 条回归测试先红后绿（修复前 integration 39 通过/11 失败 → 修复后 50/50）。明细见 `LOCAL_PATCHES.md` 与 [CHANGELOG.md](CHANGELOG.md)。

## 许可与义务

| 对象 | 许可 | 义务 |
|---|---|---|
| 本工程（集成层、统一 CLI、评测协议） | MIT（`LICENSE`：Copyright (c) 2026 Six Volumes contributors） | 保留许可与版权声明 |
| 六个上游 vendored 库 | 各自 MIT（`vendor/<component>/LICENSE` 与 wheel 内 `sixvolumes/data/licenses` 保留） | 保留版权与许可声明；不冒称上游新版本 |
| 演示文档/引用/测试题（`src/sixvolumes/data/demo`） | 本工程原创合成，MIT | — |
| 外部评测数据（CMRC2018，commit c0eb1b6） | **CC BY-SA 4.0**（不按工程 MIT 重新授权） | 署名、相同方式共享、变更说明 |
| BGE-small-zh-v1.5（仅推理，未训练） | MIT | 保留 LICENSE |
| 评测依赖（jieba 0.42.1、tiktoken、langchain-text-splitters 1.0.0、chonkie 1.3.1、presidio_analyzer 2.2.360 等） | 逐项见 `DEPENDENCIES.json` 与 `third_party/licenses`（如 colorama 0.4.6 为 BSD-3-Clause） | 保留版权、许可和 NOTICE |

义务以对应许可原文为准；分发需保留各自版权、许可和 NOTICE。

## 维护计划（摘要）

- **发版节奏**：月度窗口发版（小修复随时发 patch），版本号遵循语义化版本；每次发版走 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)。
- **Issue 驱动**：独立反馈的 11 项待修复事项逐条转 issue，进度在 issue 内公开更新；反馈响应承诺（首次回应 48 小时内）与完整文本见 [ROADMAP_维护计划.md](ROADMAP_维护计划.md)。
- **上游联动**：每季度核对一次 docling / presidio 等上游版本；presidio#2397 已合并，评估切换上游原生 opt-in 归一化实现（默认行为不变）。
- **协议冻结**：480 例合成 PII 注入与 120 条阴性对照、238 题检索评测等冻结评测集不得为发版而改动；协议修订逐条记入 `evaluation/protocol_amendments.json`。
- **停更条件（诚实声明）**：维护能力终止时，仓库将转为公开只读存档并发布最终公告，不无声停更。完整文本见 [ROADMAP_维护计划.md](ROADMAP_维护计划.md)。

## 文档导航

| 文档 | 内容 |
|---|---|
| `docs/EVIDENCE_LIMITS.md` | 证据边界与接入协议：坐标系、哈希语义、未补齐的外部验证 |
| `docs/VALIDATION.md` | 集成验收记录与预算修复复验（2026-10-23 / 10-24） |
| `docs/CORE_RESOURCES.md` / `CORE_RESOURCES.json` | 六库版本、来源、许可逐项清单 |
| `docs/THIRD_PARTY.md` | 14 个评测依赖的许可与义务 |
| `LOCAL_PATCHES.md` | 本地集成修复（含 2026-11-14 PII 修复条目） |
| `UPSTREAM_PROVENANCE.json` | 六库归档 SHA-256 与逐文件哈希 |
| `LOCAL_CHANGES.json` | 相对上游的逐文件差异（`scripts/package_release.py` 生成） |
| `CHANGELOG.md` | 版本时间线 |
| `ROADMAP_维护计划.md` | 发版节奏、issue 清单、响应承诺、停更条件 |
| `CONTRIBUTING.md` | 缺陷报告模板、PR 流程、评测协议冻结规则 |
| `RELEASE_CHECKLIST.md` | 发版前检查单 |
