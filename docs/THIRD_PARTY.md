# 资源清单（本集成发行版）

| 资源 | 版本/标识 | 来源 | 许可或条款 | 用途与边界 |
|---|---|---|---|---|
| Python | 3.10+，本次验证3.12.14 | python.org | PSF-2.0 | 标准库运行时 |
| Helan / Worddael / Gewita / Siftan / Tellan / Sothstan | 六个2026-10-23 main下载归档，以UPSTREAM_PROVENANCE.json中的SHA-256固定 | github.com/cloudydreamland，逐库URL在manifest | MIT，六份原LICENSE均保留 | vendored业务实现，工程修复见LOCAL_PATCHES.md |
| pytest | 9.1.1 | pypi.org/project/pytest | MIT | 测试，不是核心运行依赖 |
| jieba | 0.42.1 | pypi.org/project/jieba | MIT | 显式evaluation配置分词，核心不依赖 |
| tiktoken | 0.14.0 | pypi.org/project/tiktoken | MIT | 可选精确分词器测试；限定支持模型族 |
| tiktoken词表 | cl100k_base / o200k_base，缓存文件哈希随离线包记录 | tiktoken官方get_encoding下载位置 | 按上游词表及软件许可 | 明确预热后离线测试，不是模型身份真值 |
| setuptools / wheel | 构建环境安装版本记录在构建日志/环境清单 | pypi.org | MIT | 构建工具，不是核心运行依赖 |
| langchain-text-splitters | 可选adapter组1.0.0 | pypi.org | MIT | 未安装时4条第三方adapter测试如实skip，不影响统一管线核心 |
| 内置演示文档/引用/测试题 | 2026-10-23原创合成 | 本工程src/sixvolumes/data/demo | MIT | 演示与工程回归，不充当真实客户/独立基准 |
| 上游历史小说吞吐实验 | Project Gutenberg pg24264 | 见vendor/worddael/tools/dogfood.py与历史报告 | 原始作品公版，分发还需保留来源及平台条款 | 本交付未附下载语料，相关回归如实skip；本次没有重新声称历史吞吐数字 |

核心检测逻辑与上游边界都可追溯。AI辅助参与集成代码、文档和回归测试草稿，全部由实际命令运行验证与审查；未将生成文本当成客户采用或外部测量证据。

测试依赖的传递包版本与许可见 `DEPENDENCIES.json`；wheelhouse/evaluation 如存在包含本环境对应的离线测试wheels，核心wheel通用于Python3，部分可选wheel仅适合Windows CPython3.12。

六库逐项版本/来源/用途见 `docs/CORE_RESOURCES.md` 与 `CORE_RESOURCES.json`，归档以完整SHA-256标识。14个评测依赖的原许可与NOTICE保存在 `third_party/licenses`，`DEPENDENCIES.json`记录原安装路径、保留路径和SHA-256。colorama 0.4.6按实际LICENSE核实为BSD-3-Clause；tiktoken为MIT。许可证全文保留，不把全文塞入短标识字段。分发需保留各自版权、许可和NOTICE，具体义务以对应原文为准。
