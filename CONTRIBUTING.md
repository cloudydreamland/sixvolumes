# 贡献指南（CONTRIBUTING）

感谢愿意让这个证据管线变得更好。一句话行为准则：**对证据诚实，对反馈者尊重**——不夸大测试覆盖与判定范围、引用他人反馈时原样保留措辞、讨论限于事实与可复现内容（本仓库整体遵循 Contributor Covenant 社区契约的精神：友善、包容、就事论事）。

## 一、缺陷报告（Issue 模板）

提交缺陷请直接复制以下模板填写。**最小复现样例是硬要求**：没有可复现样例的缺陷报告无法进入修复队列。

```markdown
### 环境信息
- 操作系统 / Python 版本：
- 安装方式（pip install sixvolumes-trust-pipeline / 源码 run.py）：
- 包版本（`python -m sixvolumes --version` 或 `sixvolumes --version`）：

### 复现命令
（完整命令行，含全部参数，可原样粘贴运行）

### 最小复现样例
- 输入文本片段（必须可复现，几行即可）：
- 期望结果：
- 实际结果（含退出码、report.html 对应条目或 JSON 字段摘录）：

### 补充
- 是否拦截网络后复跑过（如有 `evidence_sha256` 请一并附上）：
- 其他说明：
```

最小样例要求与注意事项：

1. **可复现优先**：附最小输入文本片段与完整命令；"我有一个很长的文档不行"无法定位，请裁剪到仍能触发问题的最小片段。
2. **不要粘贴真实敏感信息**：输入样例请使用合成/打码值（如 `138-0000-0000`、合成身份证号）。报告脱敏缺陷时尤其注意——贴出真实 PII 等于把隐私交给公开仓库。
3. 附上退出码（0/1/2/3）与 report.json 中对应卷的 `status`/`limitations` 字段，能大幅加快定位。
4. 功能建议类 issue 不需要最小样例，但请说明使用场景与期望的判定行为（`passed/failed/unavailable/error` 哪一种、退出码如何）。

## 二、PR 流程

1. **先开 issue 再提 PR**（除非是文档错字级修改）：说明问题或动机，等待维护者确认方向，避免与路线图（`ROADMAP_维护计划.md`）重复。
2. Fork → 建分支（建议 `fix/<issue号>-<短描述>` 或 `feat/<短描述>`）→ 改动。
3. 本地全量回归通过（见第四节），PR 描述中给出：动机、改动清单、测试证据（命令与结果摘要）、对 `CHANGELOG.md` 的更新。
4. 涉及 `vendor/` 六库的改动必须：在 `LOCAL_PATCHES.md` 增加条目（日期、根因、修法、测试），并接受由 `scripts/package_release.py` 重算的 `LOCAL_CHANGES.json` 逐文件差异登记；不得修改归档哈希登记（`UPSTREAM_PROVENANCE.json`）来"适配"改动。
5. 提交前自查：不引入核心运行时依赖（`pyproject.toml` 的 `dependencies = []` 保持为空）、不新增联网调用（唯一外部调用入口是用户显式提供的 sothstan 配置且加 `--allow-live`）、不把 skip 改成 pass、不放宽退出码语义。
6. 维护者评审合并。CI 覆盖 8 个配置（ubuntu/windows × Python 3.10–3.13），PR 必须全绿。

## 三、评测协议冻结规则（不可协商项）

- **冻结评测集不得改动**：`evaluation/protocol.json`（protocol_version `1.0-before-first-run`）及其覆盖的 480 条合成 PII 注入（120 篇 CMRC2018 背景 × 4 类实体 × 4 形态）、120 条无效格式阴性对照、40 校准 / 120 保留 / 40 非成员对照划分、238 题/120 篇检索评测与 Siftan 阈值网格，**不得为了让数字变好而修改**。
- 确有必要的协议变更（如上游 API 变更导致原写法无法运行，且算法与结论不受影响）：必须逐条记入 `evaluation/protocol_amendments.json`（`change` + `reason`），在 PR 中单独说明，并申明是否影响任务结论。
- 修复类改动在冻结集上的重跑只能表述为**工程回归**，不得表述为"新的独立验证"或"独立保留集成绩"。
- 已发布的历史结果文件（`evaluation/results/` 等）不回写；新结果另存并附运行命令与环境。
- 跳过的测试（skip）如实报告，不计作通过；跨配置（core/evaluation）测试数字不相加冒充更大规模。

## 四、Commit 与测试规范

**Commit**

- 一件事一个 commit，信息用英文祈使句或中文均可，但需能看懂改了什么，例如：`helan: recognize dash-grouped phone numbers (3-4-4), keep segment gate`。
- 禁止在 commit 中混入：`.bak_*` 回滚辅助文件、`outputs/` 下的运行产物、tokenizer 缓存、密钥或真实 PII（它们也本就不应进入版本库）。

**测试**

- 每个缺陷修复必须携带回归测试，且**先红后绿**：在旧代码上运行新测试应失败，修复后通过；两条输出建议留档到 `outputs/validation/<run-label>/`（用 `--run-label` 与原始全量记录分开）。
- 提交 PR 前本地必须通过：

```powershell
python -m pip install ".[test]"
python scripts/verify_all.py --profile core          # 退出码 0
python -m pip install ".[evaluation]"
python scripts/verify_all.py --profile evaluation    # 退出码 0（需 jieba/tiktoken）
```

- core profile 显式屏蔽 jieba/tiktoken，用于保证核心零依赖可用；evaluation 使用 `requirements-evaluation.txt` 固定版本。两者数字不可相加宣称规模。
- 新增实体的判定行为需与四态语义一致：无证据时输出 `unavailable` 并在 `limitations` 写明原因，不以零检测项冒充通过；`passed` 的含义严格限定在该检查文档化范围内。
- 涉及报告哈希链/偏移不变量的改动，需附断网复跑 `evidence_sha256` 一致的证据。

## 五、文档与权利边界

- 改动行为时同步更新：`README.md`（若有使用面变化）、`CHANGELOG.md`（[未发布] 节）、`docs/EVIDENCE_LIMITS.md`（若边界变化）、`LOCAL_PATCHES.md`（若触及 vendor）。
- 新引入任何依赖（含测试依赖）：登记 `DEPENDENCIES.json`，许可全文存入 `third_party/licenses`；与既有依赖同版本冲突时先开 issue 讨论。
- 本工程 MIT；不要将 CC BY-SA 4.0 数据（如 CMRC2018 衍生评测数据）按 MIT 重新授权，也不要在仓库中提交无再分发授权的内容。
