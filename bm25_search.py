#!/usr/bin/env python3
"""
BM25 语义搜索引擎 — 零依赖（仅 numpy）
关键词搜索无结果时作为语义兜底

用法:
  from bm25_search import BM25Search
  bm = BM25Search()
  bm.fit(documents)       # documents = [{"id":"...","text":"...", ...}]
  results = bm.search("齿轮齿条往复", top_k=3)
"""
import json, re, math, time
from pathlib import Path
from collections import Counter


def tokenize(text):
    """中文分词：字符bi-gram + 单字 + 英文/数字词 + 中文连续词
    
    对中文技术文档，bi-gram 平衡了匹配精度和召回率。
    """
    text = text.lower()
    
    # 纯中文区域
    cn_chars = list(re.findall(r'[\u4e00-\u9fff]', text))
    
    # 英文/数字/符号词
    en_words = re.findall(r'[a-zA-Z0-9.+\-/%°#≤≥×±→℃]+', text)
    
    tokens = set()
    
    # 单字符
    for c in cn_chars:
        tokens.add(c)
    
    # 连续汉字序列的 bi-gram
    cn_seq = ''.join(cn_chars)
    for i in range(len(cn_seq) - 1):
        tokens.add(cn_seq[i:i+2])
    
    # 3-gram（只保留常见的，帮助匹配三字词）
    for i in range(len(cn_seq) - 2):
        tokens.add(cn_seq[i:i+3])
    
    # 英文/数字词
    for w in en_words:
        if len(w) >= 2:
            tokens.add(w)
            # 拆数字前缀（"45钢"→"45")
            num_m = re.match(r'^(\d+)([a-z\u4e00-\u9fff].*)', w)
            if num_m:
                tokens.add(num_m.group(1))
    
    return list(tokens)


class BM25Search:
    """零依赖 BM25 搜索引擎"""
    
    def __init__(self, k1=1.2, b=0.75, cache_path=None):
        self.k1 = k1
        self.b = b
        self.cache_path = cache_path
        self.documents = []
        self.corpus_size = 0
        self.avgdl = 0
        self.doc_lens = []
        self.idf = {}
        self.doc_terms = []  # [Counter({term: count}), ...]
        self.is_fitted = False
    
    def fit(self, documents, text_key="text"):
        """构建 BM25 索引"""
        t0 = time.time()
        self.documents = documents
        self.corpus_size = len(documents)
        
        # 分词汇总
        self.doc_terms = []
        term_freq = {}  # term -> 出现文档数
        self.doc_lens = []
        
        for doc in documents:
            txt = doc.get(text_key, "")
            tokens = tokenize(txt)
            cnt = Counter(tokens)
            self.doc_terms.append(cnt)
            self.doc_lens.append(len(tokens))
            
            for t in cnt:
                term_freq[t] = term_freq.get(t, 0) + 1
        
        self.avgdl = sum(self.doc_lens) / max(self.corpus_size, 1)
        
        # 计算 IDF
        N = self.corpus_size
        self.idf = {}
        for term, df in term_freq.items():
            self.idf[term] = math.log10(1 + (N - df + 0.5) / (df + 0.5))
        
        self.is_fitted = True
        
        if self.cache_path:
            self._save_cache()
        
        print(f"  📚 BM25 索引: {len(self.idf)} 词, {self.corpus_size} 文档, avgdl={self.avgdl:.0f}", file=__import__('sys').stderr)
        print(f"  ⏱ {(time.time()-t0)*1000:.0f}ms", file=__import__('sys').stderr)
        return self
    
    def search(self, query, top_k=5, min_score=0.01):
        """BM25 检索"""
        if not self.is_fitted or not query.strip():
            return []
        
        t0 = time.time()
        q_tokens = tokenize(query)
        
        scores = [0.0] * self.corpus_size
        used_terms = 0
        
        for qt in q_tokens:
            if qt not in self.idf:
                continue
            used_terms += 1
            idf_val = self.idf[qt]
            k1 = self.k1
            b = self.b
            
            for i in range(self.corpus_size):
                tf = self.doc_terms[i].get(qt, 0)
                if tf == 0:
                    continue
                doc_len = self.doc_lens[i]
                score_part = idf_val * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / self.avgdl))
                scores[i] += score_part
        
        if used_terms == 0:
            return []
        
        # 排序取 top_k
        top_indices = sorted(range(self.corpus_size), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            score = scores[idx]
            if score < min_score:
                break
            doc = dict(self.documents[idx])
            doc["bm25_score"] = round(score, 4)
            results.append(doc)
        
        return results
    
    def _save_cache(self):
        if not self.cache_path:
            return
        try:
            cache = {
                "k1": self.k1, "b": self.b,
                "avgdl": self.avgdl,
                "corpus_size": self.corpus_size,
                "idf": self.idf,
                "doc_lens": self.doc_lens,
                "doc_terms": [{str(k):v for k,v in cnt.items()} for cnt in self.doc_terms],
                "documents": self.documents,
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception as e:
            print(f"  ⚠️ 缓存写入失败: {e}", file=__import__('sys').stderr)
    
    def load_cache(self):
        if not self.cache_path or not Path(self.cache_path).exists():
            return False
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            self.k1 = cache.get("k1", 1.2)
            self.b = cache.get("b", 0.75)
            self.avgdl = cache["avgdl"]
            self.corpus_size = cache["corpus_size"]
            self.idf = cache["idf"]
            self.doc_lens = cache["doc_lens"]
            self.doc_terms = [Counter(cnt) for cnt in cache["doc_terms"]]
            self.documents = cache["documents"]
            self.is_fitted = True
            return True
        except Exception as e:
            print(f"  ⚠️ 缓存加载失败: {e}", file=__import__('sys').stderr)
            return False


if __name__ == "__main__":
    docs = [
        {"id":"doc1", "text":"齿轮齿条机构常用于往复运动，载荷大、行程长。齿轮模数通常取6-8mm。"},
        {"id":"doc2", "text":"深沟球轴承适用于高速轻载场合，摩擦小。"},
        {"id":"doc3", "text":"45号钢调质处理硬度可达HRC30-35，综合性能优良。"},
        {"id":"doc4", "text":"V带传动适合中心距较大的场合，传动比一般不超过7。"},
        {"id":"doc5", "text":"液压缸推力计算：F=pA，适用于重载直线运动。"},
    ]
    
    bm = BM25Search()
    bm.fit(docs)
    
    for q in ["齿轮齿条往复", "轴承高速", "45号钢硬度", "液压缸推力", "直线运动"]:
        r = bm.search(q, top_k=2)
        print(f"'{q}' → {[d['id'] for d in r]}")
        for d in r:
            print(f"    {d['bm25_score']:.4f} → {d['text'][:40]}")