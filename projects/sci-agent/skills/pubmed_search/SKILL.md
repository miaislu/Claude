---
name: pubmed-search
description: Search PubMed for biomedical literature using NCBI E-utilities API. Use when the user asks to find papers, review literature, or search for research on a biomedical topic.
tools:
  - pubmed_search
  - fetch_abstract
license: MIT
---

# PubMed Search Skill

通过 NCBI E-utilities API 检索 PubMed 文献数据库。

## 使用场景

- 查找特定主题的研究论文
- 获取论文摘要和元数据
- 统计某个领域的发表量

## 工具说明

### pubmed_search
搜索 PubMed，返回匹配的 PMID 列表。
- `query`: 搜索词，支持 MeSH 术语和布尔运算符
- `max_results`: 最多返回结果数（默认 10，最大 100）

### fetch_abstract
根据 PMID 获取论文摘要和元数据。
- `pmid`: PubMed ID

## 示例

```
用户: 帮我搜索 2023 年以来关于 CRISPR 癌症治疗的论文
工具调用: pubmed_search(query="CRISPR cancer therapy", max_results=10)
然后: fetch_abstract(pmid=<each_pmid>)
```
