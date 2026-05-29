# 📚 机械设计手册知识库

> 基于《机械设计手册》第六版（成大先 主编，化学工业出版社）构建的可检索知识库系统。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/nasplycc/mechanical-design-handbook)](https://github.com/nasplycc/mechanical-design-handbook/stargazers)

## 🎯 功能概览

| 方式 | 速度 | 说明 |
|:----|:----:|:-----|
| **Web 界面** | ~12ms | 浏览器搜索，支持公式渲染(KaTeX)、PDF一键跳转指定页 |
| **设计向导** | ~53ms | 输入自然语言需求，自动生成带页码引用的设计报告 |
| **MCP 服务** | ~7ms | 集成到 AI 对话中直接查询 |
| **CLI 搜索** | ~5ms | 关键词搜索 + BM25 语义检索兜底 |

## 🏗️ 架构

```
机械设计手册检索系统
├── 机械设计知识库/          ← 59 个已标注 MD 文件（精华+深化版）
│   ├── 00_速查表/           ← 常用材料、传动效率、配合、硬度等速查
│   ├── 01_设计基础/         ← 力学公式、公差配合、制图标准
│   ├── 02_材料工程/         ← 黑色/有色金属、热处理、非金属材料
│   ├── 03_制造工艺/         ← 铸造、锻造、冲压、焊接、机加工
│   ├── 04_零部件设计/       ← 轴承、弹簧、螺纹、润滑密封、电机
│   ├── 05_传动系统/         ← 齿轮、带链、减速器
│   ├── 06_流体传动/         ← 液压传动、气压传动
│   ├── 07_人机与结构/       ← 机构设计、机架设计、振动控制
│   └── 08_标准索引/         ← 页码对照表、GB/JB 标准清单
│
├── web_ui.py               ← Web 界面 (localhost:5231)
├── search.py               ← 核心检索引擎（关键词+BM25语义兜底）
├── wizard.py               ← 设计向导（10种设计场景自动识别）
├── mcp_server.py           ← MCP stdio 服务
├── bm25_search.py          ← BM25 语义搜索引擎（纯 numpy 零依赖）
├── pdf_annotate.py         ← PyMuPDF 精确页码标注
├── run.sh                  ← 统一入口
└── citation_search.py      ← 标注评论搜索（备用）
```

## 🌐 在线访问 (GitHub Pages)

无需部署，直接访问：

**https://nasplycc.github.io/mechanical-design-handbook/**

客户端侧 BM25 搜索，52 个知识库文件 76KB 索引，纯前端检索。

## 🚀 本地启动

```bash
# Web 界面
./run.sh web
# → http://localhost:5231

# 设计向导
./run.sh design "齿轮齿条 10000N 3m"

# CLI 搜索
./run.sh cli "45号钢调质硬度"

# MCP 服务
./run.sh mcp
# → mcporter call mechanical-design.mechanical_search query="..."
```

> 重新生成静态索引: `python3 build_static_index.py`（更新知识库后需要重新生成索引同步到 GitHub Pages）

## 📖 数据来源

《机械设计手册》第六版 第1~5卷 — 成大先 主编，化学工业出版社，2016 年出版。

- **总页数**: 8512 页（2017+1693+1640+1316+1846）
- **篇数**: 23 篇（一般设计资料 ~ 气压传动）
- **知识库**: 59 个 MD 文件，所有标题已标注精确或范围页码引用
- **页码标注率**: 98.8%（3307/3307 标题）

> ⚠️ **版权声明**: 本仓库仅包含**自行整理的知识库文本摘要**（Markdown 格式）。
> 原始 PDF 文件（受版权保护）**不包含在本仓库中**。
> 如果您拥有该手册的合法副本，可将 PDF 置于项目根目录使用 PDF 跳转功能。

## 🔧 技术亮点

- **BM25 语义检索**: 零外部依赖，纯 numpy 实现的 BM25 引擎（228k 词汇表，1.2s 建索引）
- **精确页码跳转**: Web 界面点击页码 → 浏览器自动打开 PDF 到对应页面（支持 Range 分段下载）
- **公式渲染**: 集成 KaTeX CDN，LaTeX 公式自动渲染
- **设计向导**: 自动识别 10 种设计场景（齿轮齿条、V带、轴承、液压等），提取参数并输出分步报告
- **Git 版本管理**: 知识库、检索脚本全量纳入版本控制

## 💡 使用场景

- 🔩 **机械设计工程师**: 快速查询标准数据、公式、选型表
- 🎓 **机械专业学生**: 课程设计、毕业设计的参考手册
- 🤖 **AI 辅助设计**: 通过 MCP 集成到 AI 工作流中
- ⚙️ **产品研发**: 标准件选型、材料选择、强度校核

## 📝 License

MIT