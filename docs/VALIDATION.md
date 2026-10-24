# 集成验收记录（2026-10-23）

以 `outputs/validation/{core,evaluation}/results.json`、逐库JUnit XML及原始log为机器证据。Python 3.12.14，pytest 9.1.1；同一批用例在两个环境配置运行，不能把两次运行相加宣称独立测试规模。

| 配置 | 集成 | Helan | Worddael | Gewita | Siftan | Tellan | Sothstan | 合计 |
|---|---|---|---|---|---|---|---|---|
| core，无jieba/tiktoken | 24通过 | 202通过 | 202通过/8跳过 | 181通过 | 20通过 | 149通过/2跳过 | 65通过 | 843通过、10跳过、0失败 |
| evaluation，jieba0.42.1/tiktoken0.14.0 | 24通过 | 202通过 | 205通过/5跳过 | 181通过 | 20通过 | 151通过 | 65通过 | 848通过、5跳过、0失败 |

evaluation的5条跳过：4条需要额外LangChain adapter依赖，1条需要上游未随仓库提供的小说语料。core另跳过可选分词器集成；门禁和依赖缺失行为仍有测试，未将skip伪装成通过。

24条集成回归覆盖：四卷可执行/两卷缺证据、真实进程失败退出码、污染注入、假引语、严格缺证据退出3、输入错误、原文与脱敏坐标系、CRLF、Vault明文隔离、HTML转义、报告哈希篡改、core分词不受可选包影响、规范化正例及不跨行/双空白反例。模型真实端点验证不在本记录内，mock自检只验证工程链路。

Tellan代理错误原因为系统代理未绕过loopback；已在保留外部代理配置的前提下修复本地路由，并以坏代理环境回归验证。Worddael固定profile后报告可按字节重建，原先的jieba历史报告另存，未覆盖原始审计目录。

## 硬预算修复后局部复验（2026-10-24）

上表是修复前实际完整运行记录，保留不覆盖。随后冻结外测发现Worddael标点处理使4块达257字（预算256），仅修改受影响的分块实现并重跑集成与Worddael模块，其余五库未重复运行。命令为 `python scripts/verify_all.py --profile core --components integration worddael --run-label budget-fix`；evaluation仅替换profile。原始命令、环境、JUnit与日志见 `outputs/validation/budget-fix/{core,evaluation}`。

| 配置 | 集成 | Worddael | 本次受影响模块合计 |
|---|---|---|---|
| core | 25通过 | 208通过/8跳过 | 233通过、8跳过、0失败 |
| evaluation | 25通过 | 211通过/5跳过 | 236通过、5跳过、0失败 |

新增6条Worddael回归覆盖满额后闭标点、开标点挤占相邻块、1字预算、超长原子句、overlap实际复用和固定种子边界压力；1条新增集成回归检查最终落盘分块与报告完整性。原有预算断言由+2/额外overlap容忍收紧为硬上限；相邻两块都满额、无法调整边界时明确以预算和完整覆盖为先。

见过失败后的只读工程重放：同一120文档、313块，超限0、最大256字、偏移错误0、遗漏字符0，记录见 `outputs/validation/budget-fix/seen-data-replay.json`。其中保存冻结原指标4个超限/最大257及原文件SHA-256，并检查原文件未变。此重放不能视为新独立保留集，未重测RAG质量、未调整Siftan阈值。

若将未修改模块此前已通过记录与本次复验组成累计覆盖清单，对应core850通过/10跳过，evaluation855通过/5跳过；这不是新一轮全量执行数字，两个配置仍不可相加。集成+六库现在共860个工程用例。
