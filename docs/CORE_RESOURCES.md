# 六库本版来源清单

集成发行版0.2.0。六个上游pyproject均声明0.1.0；本地补丁另列，不能把main归档当成已发布新版本。来源于2026-10-23下载的main，归档SHA-256固定来源内容。

| 包 | 上游声明版本 | 来源 | 许可/用途 |
|---|---|---|---|
| siftan | 0.1.0 | [TheSieveBeneathTheStars](https://github.com/cloudydreamland/TheSieveBeneathTheStars) | MIT / 可选污染筛查 |
| helan | 0.1.0 | [TheVeilOfHiddenNames](https://github.com/cloudydreamland/TheVeilOfHiddenNames) | MIT / 中文脱敏与原文偏移 |
| gewita | 0.1.0 | [WitnessesInTheMargins](https://github.com/cloudydreamland/WitnessesInTheMargins) | MIT / 引用格式与引语对齐 |
| worddael | 0.1.0 | [TheDaleOfRememberedWords](https://github.com/cloudydreamland/TheDaleOfRememberedWords) | MIT / 结构分块 |
| tellan | 0.1.0 | [TheLedgerOfVanishingTokens](https://github.com/cloudydreamland/TheLedgerOfVanishingTokens) | MIT / 可选token对账与链一致性 |
| sothstan | 0.1.0 | [TheTrialOfTheHiddenVoice](https://github.com/cloudydreamland/TheTrialOfTheHiddenVoice) | MIT / 可选模型身份统计证据 |

逐库完整归档哈希、用途、原LICENSE路径和义务见根目录CORE_RESOURCES.json；原始逐文件哈希见UPSTREAM_PROVENANCE.json；当前改动见LOCAL_CHANGES.json。六份原MIT许可随源码和wheel保留。

测试/评测14个依赖的版本、来源、SPDX表达式、用途、修改说明、义务和原许可文件SHA-256见DEPENDENCIES.json，许可全文保存在third_party/licenses。colorama 0.4.6经安装发行包LICENSE.txt核实为BSD-3-Clause；tiktoken字段归一为MIT，原全文单独保留。jieba发行包未附LICENSE，补保留其对应v0.42.1源码标签原许可。
