# 外部公开数据评测（摘要）

完整协议、逐项输出与错误样例见 [`evaluation/评测报告.md`](evaluation/评测报告.md)（冻结协议 `evaluation/protocol.json`，环境与哈希 `evaluation/results/environment.json`，完整性校验 `evaluation/verify_integrity.py`）。

## 可引用结果速览

| 模块 | 设置 | 结果 | 诚实边界 |
|---|---|---|---|
| Worddael 切块 | CMRC2018 冻结切片，120 篇 / 238 题 | 与合理中文配置的 LangChain、Chonkie 打平（Recall@1 90.756%）；固定 256 字基线 Recall@1 略高 | 优势区间 [0, 4.219]pp 含 0，不宣称可靠优势 |
| Helan 脱敏 | 480 条合成注入 PII × 4 类形态 | 原生 37.5% → 规范化视图 100%，0/120 误报 | 合成构造扰动鲁棒性，不是真实 PII 召回率；对照 Presidio 适配器打平，缺口定位在输入规范化 |
| Siftan 污染筛查 | 120 条插入扰动保留样例 | 原生精确层 0/120 → 校准阈值 0.15 后 120/120；非成员对照 0% | 阈值为实验侧 advisory；20 篇对照中 3 篇存在 13-gram 字面重合，未定性为污染 |
| Gewita 引用核查 | 4 篇真实 DOI 走真实 Crossref 接口 | 存在性 4/4 EXISTS；年份篡改 4/4 SUSPECT | 样本量小；参考文献字符串由元数据渲染，非自然格式样本 |

## 复现

```powershell
cd evaluation
python -m venv .venv
python -m pip install -r requirements.lock.txt
python download_model.py
./replay.ps1
```

模型权重经 `download_model.py` 按卡内 SHA-256 下载（约 91 MB，未随仓库分发）；语料衍生文件与许可见 `evaluation/data/`；四个自研库以 `evaluation/source_snapshot/` 哈希为准。评测为本地冻结协议实验，不是第三方认证。
