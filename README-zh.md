# MinFa-RAG-flash

基于检索增强生成（RAG）的轻量《民法典》问答系统。用自然语言提问，得到引用具体法条的专业回答。

> **核心课题**：通过优化检索质量与提示词设计，让免费的 flash 级小模型在法律问答任务上逼近次旗舰模型的效果——用可量化的评测数据证明「好 RAG 能压缩模型差距」。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

## 🔮 功能特性

- 🔍 **条文级检索** —— 按「第 X 条」结构精准切分《民法典》，检索天然对齐法条单位
- 💬 **自然语言问答** —— 通俗提问，专业回答，附带法条引用
- 🎯 **引用溯源** —— 每个答案标注对应法条出处与相似度，可核对
- ⚡ **零成本运行** —— 免费 flash LLM API + 本地向量模型，全链路不花钱
- 🌐 **REST API** —— FastAPI 后端，可独立部署，也可作为其他 Agent 系统的工具被调用

## ⭕ 为什么叫 MinFa-RAG-flash？

作者偏爱 "flash" 类 LLM——小、快、性价比高。大模型厂商的旗舰模型效果最好，但成本高；flash 级模型便宜甚至免费，但知识面与推理能力有限。

本项目想验证的想法是：**如果 RAG 系统做得足够好（检索准、切分对、提示词调优到位），可以让「过时」的 flash 模型发挥出略逊于次旗舰模型的效果。**

这便是本项目存在的意义。

后续会用同一套评测题集，对 flash 模型与旗舰模型做横向对比，评测结果将发布在「性能指标」一节。

## 🚀 快速开始

> ⚠️ 开发中，以下为预期使用方式（功能完成后生效）。

### 环境要求

- Python 3.10+
- 一个智谱 AI 的 API Key（[免费注册获取](https://open.bigmodel.cn/)）

### 安装

```bash
git clone https://github.com/3165zz/MinFa-RAG-flash.git
cd MinFa-RAG-flash

# 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
```

### 配置

在项目根目录创建 `.env` 文件：

```
ZHIPU_API_KEY=你的key
```

### 使用

```bash
# 首次运行：构建《民法典》向量知识库
python build_index.py

# 启动问答
python main.py
```

按提示输入法律问题，即可获得附带法条引用的回答。

## 🌆 架构

```
用户提问
   ↓
问题向量化（bge-small-zh-v1.5，本地运行）
   ↓
FAISS 相似度检索《民法典》相关法条（Top-K）
   ↓
法条 + 问题组装成提示词（Prompt）
   ↓
GLM-4-Flash 生成回答
   ↓
返回答案 + 法条引用来源
```

**技术选型一览**

| 环节 | 选型 | 理由 |
|---|---|---|
| LLM | 智谱 GLM-4-Flash | 免费 API，中文能力强，契合「flash + 性价比」理念 |
| 向量模型 | BAAI / bge-small-zh-v1.5 | 中文效果好，模型小，CPU 即可运行 |
| 向量库 | FAISS | 单机够用，轻量高效 |
| 文本切分 | 按「条」切分 | 法条天然是分块单位，检索质量高一档 |
| 后端服务 | FastAPI | 契合 REST API 集成需求，自动生成接口文档 |
| 评测（计划） | 自建题集 + flash/旗舰横向对比 | 用数据验证核心课题 |
| 应用框架（v3 起引入） | LangChain / LangGraph | 先裸写原理、再用框架重构，v5 用于 Multi-Agent 编排 |

## 📊 性能指标

（开发中，待项目成型后补充：检索命中率、回答准确率、flash 模型与旗舰模型的横向对比等）

### 示例对话（示例，功能开发中）

> **问：** 我租的房子房东没经过我同意就进门换锁，合法吗？
>
> **答：** 房东擅自进入出租房屋可能侵犯承租人的住宅安宁权与隐私权……
> - 引用：《民法典》第一千零三十二条（隐私权）· 相似度 0.88

## 🧭 Roadmap

- [ ] **v1 核心链路**：命令行问答跑通（切分 → 向量化 → 检索 → 生成）
- [ ] **v2 服务化**：FastAPI 后端 + REST API + 简单 Web 界面
- [ ] **v3 效果优化**：查询改写、混合检索（BM25 + 向量）、重排序，引入 LangChain 重构检索链
- [ ] **v4 评测验证**：自建评测题集，flash vs 旗舰模型横向对比，产出性能报告
- [ ] **v5 Agent 化**：基于 LangGraph 将 RAG 封装为工具，接入 Multi-Agent 系统（下一个项目的地基）

## 🤝 贡献

欢迎提交 Issue 与 Pull Request。

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## ⚠️ 免责声明

本系统输出仅供参考与学习用途，**不构成正式法律意见**。涉及具体法律事务，请咨询专业律师。