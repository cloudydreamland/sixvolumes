# 六卷书 · 中文知识库证据管线

六个公开 MIT 工具库的可安装集成发行版。输入 UTF-8 中文知识库，输出脱敏文本、可追溯切块、引用核对、可选基准筛查、可选账本/模型审计，以及一份离线可读的 JSON + HTML 报告。核心无需第三方运行依赖，也不调用外部 API。

## 一条命令演示

```powershell
python run.py demo -o outputs/demo-clean
```

打开 `outputs/demo-clean/report/report.html`。在已安装环境也可执行 `sixvolumes demo -o demo`。演示数据为原创合成样例，不是真实客户案例或独立效果验证。

默认结果应为 `partial`：Helan、Worddael、Gewita、Siftan 已执行；没有真实调用账本和官方模型基线时，Tellan、Sothstan 显示 `unavailable`。这不是六卷全部通过。

```powershell
python run.py demo -o outputs/demo-negative --scenario contaminated
python run.py demo -o outputs/demo-bad-quote --scenario bad-quote
python run.py demo -o outputs/demo-strict --require-all
```

前两条应返回退出码 1，严格模式因缺少两卷证据返回 3。程序没有为了演示而伪造真实 API 结果。

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

## 六卷如何连起来

1. 读入原始字节并计算 SHA-256。原文仅保留在本机输入目录。
2. Helan 检测实体；集成层可用有界 Unicode 规范化补充格式变体识别。用 Vault 占位符替换并实际验证还原闭环。默认不保存 Vault。
3. Worddael 对脱敏文本切块，验证 `chunk.text == masked[start:end]`，每块附转换段到原文字符范围的映射。偏移单位是 Unicode 字符，不是 UTF-8 字节。
4. Gewita 解析参考文献格式，并把显式提供的引语对齐到给定原始来源；规范化逐字命中也会单独标出 `exact_literal`。
5. 若提供 `--contamination-index benchmark.tsi`，Siftan 在**脱敏前原文**上筛查，避免隐私替换掩盖重叠。索引必须是真实使用者提供；CLEAN 只限于该索引的字面检测范围。
6. 若提供 `--ledger api.jsonl`，Tellan 校验哈希链并以明确的 heuristic 模式对账。若提供 `--sothstan-config model.json --allow-live`，Sothstan 使用非 demo 官方基线做有限预算行为审计。

所有步骤统一为 `passed / failed / unavailable / error`；机器报告保留输入哈希、索引哈希、来源和限定语。HTML 完全自包含，不加载外部字体或脚本。

## 预研：NegQuote 否定感知引语门控

外部公开数据评测发现：引语中加入"并非/没有"类否定词后，Gewita 仍可能给出 NEAR（近逐字）裁决——引语说了反话，词面却近乎逐字命中。基于"LLM 否定理解不可靠"的文献共识，`preresearch/negquote/` 实现了**规则化降级**（不假装语义理解）：引语含否定线索而对齐片段不含时，支持性裁决降级为 `UNSUPPORTED_PENDING_REVIEW` 交人工复核。

- v0.1（215 个冻结合成探针）：最小否定编辑拦截 39/40，135 个非否定探针 0 误触发；"不+动词"线索缺口如实报告。
- v0.1.1（同集复测）：按预告扩充 16 条"不+动词"线索后，最小否定编辑拦截 **40/40**，无误触发；探针语料与门控逻辑零改动，逐条 diff 共 2 条（1 条目标类真阳性 + 1 条语义反转的正确触发）。
- 边界：合成语料上的行为描述；镜像方向未覆盖；生产可用性需 ≥300 对真实引语 + 未参与开发者的人工复核（v1.0 计划）。详见 `preresearch/negquote/REPORT.md` 与两份结果 JSON。

## 退出码与诚实边界

| 码 | 含义 |
|---|---|
| 0 | 已执行且可判定的检查无失败；总状态仍可能是 partial |
| 1 | 检查发现问题，如字面污染、无来源引语、账本损坏、行为不一致 |
| 2 | 输入或执行错误，不能当作通过 |
| 3 | `--require-all` 下存在 unavailable |

**Vault 是含原始敏感值的明文映射，不是加密或密钥。** 如确需还原，使用 `--vault-dir` 指向与报告完全分离的受保护目录；不要对外分享该目录。集成版不自研密码算法。规则脱敏可能漏检，`passed` 仅表示已执行转换与不变量校验。

`--pii-profile native` 使用冻结的原生 Helan；默认 `normalized` 增加 NFKC/零宽/孤立分隔字符的有界识别视图，保留原文偏移且不跨行拼接。该修复是在独立评测发现格式失效后新增的工程改进，**不能把同一评测集上的修复后结果冒称全新独立验证**。局限和测试见 `docs/EVIDENCE_LIMITS.md`。

哈希链和文件哈希只检查内容一致性，不是签名、身份认证或原始数据真实性证明。Tellan 内置价格为历史快照，未重新逐项核实，费用数字不可用作财务结算。Sothstan 的 AUTHENTIC 只表示与所给基线行为一致，不能排除精巧转发。

## 真正的外部证据接入

`docs/sothstan-config.example.json` 是配置模板，密钥仅通过环境变量读取，不放入配置或报告。至少需要目标和一个可混淆近邻的非 demo 官方基线。未设置 `--allow-live` 不联网，未配置不通过。默认预算最多24个请求、4000个提示token、单请求10秒；实际输出token及服务侧计费还需自行核对。

```powershell
python -m sothstan.cli collect https://OFFICIAL-ENDPOINT/v1 --model MODEL --family FAMILY --out baselines/MODEL.json --api-key-env MODEL_API_KEY
sixvolumes audit knowledge -o report --sothstan-config model.json --allow-live
```

请在隔离环境使用本发行版，它打包了六库相同顶层模块名，避免与单独安装的上游六包同时混装。

## 安装、离线使用与验证

发布于 PyPI（`pip install sixvolumes-trust-pipeline`），源码的 `run.py` 也可直接离线运行；wheel 无运行依赖：

```powershell
python -m pip install sixvolumes-trust-pipeline
python -m sixvolumes demo -o outputs/installed-demo
```

已有 Python 3.10+ 时，源码的 `run.py` 可直接离线运行。离线安装：

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

本次离线ZIP还提供Windows CPython3.12对应的 `wheelhouse/evaluation` 与 `outputs/tokenizer-cache`：`pip install --no-index --find-links wheelhouse/evaluation -r requirements-evaluation.txt` 后将 `TIKTOKEN_CACHE_DIR` 指向该缓存，可离线重跑evaluation。其他Python/系统需要自行准备相应wheels。4条LangChain适配器测试及1条外部小说测试未在本次环境启用；详见 `docs/VALIDATION.md`，跳过没有计作通过。

Worddael 内置报告默认固定 `core` 分词配置；`python -m worddael.eval.report --profile jieba` 是另一独立配置。上游原数字保存在 `vendor/worddael/benchmarks/results.upstream-jieba.md`，不与新版 core 数字混用。

`python scripts/package_release.py` 在已具备 setuptools/wheel 的环境离线构建 wheel，并生成源码清单和离线 ZIP。`UPSTREAM_PROVENANCE.json` 固定六个下载归档的SHA-256与原始文件哈希；`LOCAL_PATCHES.md` 说明集成修复。上游所有 LICENSE 均保留，wheel 内附六库许可文本。

2026-10-24修复Worddael字符上限：`max_chars`现在包含overlap和标点调整，不能以吸收标点为由超出上限；无法兼顾时优先保留完整覆盖和预算。冻结外测原始4个257字块仍保留，修复后已见数据只算工程回归，记录与局部复验计数见 `docs/VALIDATION.md`。六库版本/来源清单见 `docs/CORE_RESOURCES.md`；14个评测依赖的原许可与NOTICE随离线包保存。
