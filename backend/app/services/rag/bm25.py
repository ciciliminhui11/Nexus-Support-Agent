"""BM25 关键词检索（自研 Okapi BM25 + jieba 中文分词）。

research §1：混合检索的 BM25 路。jieba 仅承担中文分词（用户选定依赖），
打分在本模块自研实现（宪法「检索核心链路自研可读、可调优」，不引入 jieba_bm25 第三方包）。

中文关键词检索的现实问题：朴素字符一元分词会让「今天的天气怎么样」因共享
「的/么/天」等高频功能字命中无关文档，破坏「空检索走兜底」语义。因此引入
**显著词闸门**：候选片段只有与查询共享 ≥1 个「显著词」（CJK 二元及以上词
或 ASCII 单词，len≥2）才进入召回；闸门通过后，一元词仍正常参与 BM25 打分。

jieba 导入失败时降级为仅 ASCII 单词路（中文路关闭），不影响服务可用性。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

_K1 = 1.5  # BM25 词频饱和参数
_B = 0.75  # BM25 文档长度归一化参数

_CJK = re.compile(r"[一-鿿]")
_ASCII_WORD = re.compile(r"[A-Za-z0-9]+")

try:  # jieba 缺失 → 中文分支关闭（仅剩 ASCII），不崩溃
    from jieba import lcut as _jieba_lcut

    JIEBA_AVAILABLE = True
except Exception:  # noqa: BLE001
    JIEBA_AVAILABLE = False


def tokenize(text: str) -> list[str]:
    """完整 token 列表（参与 BM25 打分）。

    - ASCII 单词：正则提取（不依赖 jieba 英文分词），len≥2 小写；
    - CJK 词：剔除 ASCII 片段后交给 jieba，保留含 CJK 的 token（含单字，供打分）。
    """
    ascii_tokens = [t.lower() for t in _ASCII_WORD.findall(text) if len(t) >= 2]
    remaining = _ASCII_WORD.sub(" ", text)
    cjk_tokens: list[str] = []
    if JIEBA_AVAILABLE and remaining.strip():
        try:
            cjk_tokens = [t for t in _jieba_lcut(remaining) if _CJK.search(t)]
        except Exception:  # noqa: BLE001
            pass
    return ascii_tokens + cjk_tokens


def significant_tokens(tokens: list[str]) -> list[str]:
    """「显著词」= len≥2 的 token（CJK 二元及以上词、或 ASCII 单词）。

    单字 CJK（的/天/是/吗）与单字符 ASCII 永不显著——这是闸门不产生
    功能字假阳性的关键。
    """
    return [t for t in tokens if len(t) >= 2]


def passes_gate(query_tokens: list[str], doc_tokens: list[str]) -> bool:
    """BM25 相关性闸门：查询与候选共享至少一个显著词。"""
    return bool(set(significant_tokens(query_tokens)) & set(significant_tokens(doc_tokens)))


@dataclass
class BM25Index:
    """内存 Okapi BM25 索引：给定语料构建，按查询打分排序。

    rank() 先过显著词闸门再打分，返回 [(doc_idx, score)] 降序。
    """

    doc_tokens: list[list[str]]
    doc_tf: list[dict[str, int]]
    doc_significant: list[set[str]]
    n: int
    doc_freq: dict[str, int] = field(default_factory=dict)
    avg_dl: float = 0.0

    @classmethod
    def build(cls, texts: list[str]) -> "BM25Index":
        docs = [tokenize(t) for t in texts]
        n = len(docs)
        df: dict[str, int] = {}
        for toks in docs:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        avg_dl = (sum(len(d) for d in docs) / n) if n else 0.0
        return cls(
            doc_tokens=docs,
            doc_tf=[dict(Counter(toks)) for toks in docs],
            doc_significant=[set(significant_tokens(toks)) for toks in docs],
            n=n,
            doc_freq=df,
            avg_dl=avg_dl,
        )

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        # +1 平滑保证 df=n（出现在全部文档）时 idf 仍为正
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def rank(self, query: str, top_k: int | None = None) -> list[tuple[int, float]]:
        """返回 [(doc_idx, score)] 按分数降序，仅含通过闸门的文档。"""
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        q_significant = set(significant_tokens(q_tokens))
        results: list[tuple[int, float]] = []
        for i, toks in enumerate(self.doc_tokens):
            if not (q_significant & self.doc_significant[i]):
                continue  # 闸门：无共享显著词 → 不进入召回
            dl = len(toks)
            tfmap = self.doc_tf[i]
            s = 0.0
            for t in q_tokens:
                tf = tfmap.get(t, 0)
                if tf == 0:
                    continue
                if self.avg_dl:
                    denom = tf + _K1 * (1 - _B + _B * dl / self.avg_dl)
                else:
                    denom = tf
                s += self._idf(t) * (tf * (_K1 + 1)) / denom
            if s > 0:
                results.append((i, s))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k] if top_k else results
