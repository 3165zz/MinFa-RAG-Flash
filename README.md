# MinFa-RAG-Flash

基于检索增强生成（RAG）的轻量《民法典》问答系统。用自然语言提问，得到引用具体法条的专业回答。

> **核心课题**：通过优化检索质量与提示词设计，缩小 Flash 型 LLM 在法律问答任务上与旗舰模型的差距——用可量化的评测数据证明。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)

## 🔮 功能特性

- 🔍 **条文级检索** —— 按「第 X 条」结构精准切分《民法典》，检索天然对齐法条单位
- 💬 **自然语言问答** —— 通俗提问，专业回答，附带法条引用
- 🎯 **引用溯源** —— 每个答案标注对应法条出处与相似度，可核对

## 🚀 快速开始

### 环境要求

- Python 3.12+
- 阿里云百炼 API Key（[注册开通](https://bailian.console.aliyun.com/)）

### 安装

```bash
git clone https://github.com/3165zz/MinFa-RAG-Flash.git
cd MinFa-RAG-Flash

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
DASHSCOPE_API_KEY=你的key
```

**技术选型一览**

| 环节 | 选型 | 理由 |
|---|---|---|
| LLM | flash模型 | 高性价比 |
| 向量模型 | BAAI/bge-reranker-v2-m3 | 硅基流动免费调用 |
| 向量库 | FAISS | 单机够用，轻量高效 |
| 文本切分 | 按「条」切分 | 法条天然是分块单位，检索质量高 |


## 📊 性能指标

### 2×2 因子对照实验

课题：**当检索把正确的法条稳定送入上下文时，Flash 型 LLM 能否达到逊于旗舰模型的可用水准？**

### RAGAS

（空）

## 🧭 Roadmap

- [ ] **核心链路**：命令行问答跑通（按「条」切分 → 向量化 → FAISS 检索 → 生成）

## 🤝 贡献

欢迎提交 Issue 与 Pull Request。

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## ⚠️ 免责声明

本系统输出仅供参考与学习用途，**不构成正式法律意见**。涉及具体法律事务，请咨询专业律师。