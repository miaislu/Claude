"""PubMed 文献检索工具，通过 NCBI E-utilities 免费 API 实现。"""

import urllib.parse
import urllib.request
import json
import xml.etree.ElementTree as ET
from typing import Any


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def pubmed_search(query: str, max_results: int = 10) -> dict[str, Any]:
    """搜索 PubMed，返回匹配的 PMID 列表。"""
    max_results = min(max_results, 100)
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    })
    url = f"{ESEARCH_URL}?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    result = data.get("esearchresult", {})
    pmids = result.get("idlist", [])
    count = int(result.get("count", 0))

    return {
        "total_found": count,
        "returned": len(pmids),
        "pmids": pmids,
        "query": query,
    }


def fetch_abstract(pmid: str) -> dict[str, Any]:
    """根据 PMID 获取论文摘要和元数据。"""
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "xml",
    })
    url = f"{EFETCH_URL}?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    article = root.find(".//PubmedArticle")
    if article is None:
        return {"pmid": pmid, "error": "Article not found"}

    def get_text(element, path: str) -> str:
        node = element.find(path)
        return "".join(node.itertext()).strip() if node is not None else ""

    title = get_text(article, ".//ArticleTitle")
    abstract_parts = [
        "".join(node.itertext()).strip()
        for node in article.findall(".//AbstractText")
    ]
    abstract = " ".join(filter(None, abstract_parts))

    authors = []
    for author in article.findall(".//Author")[:5]:
        last = get_text(author, "LastName")
        first = get_text(author, "ForeName")
        if last:
            authors.append(f"{last} {first}".strip())

    year = get_text(article, ".//PubDate/Year") or get_text(article, ".//PubDate/MedlineDate")
    journal = get_text(article, ".//Journal/Title")

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": year,
        "abstract": abstract[:1500] if abstract else "No abstract available",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }
