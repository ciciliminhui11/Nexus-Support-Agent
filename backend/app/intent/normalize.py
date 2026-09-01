"""文本归一化（FR-001）：全角→半角、去空格/特殊符号、繁简转换、形近字纠错。

归一化结果仅作为规则层匹配输入（原始输入保留用于展示与入库）。
v1 的繁简映射与形近字纠错为精选基线（覆盖客服高频词），完整方案可换 OpenCC。
"""
from __future__ import annotations

import re

_FULLWIDTH_SRC = (
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～。，！？：；、"
)
_FULLWIDTH_DST = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~.,!?:;、"
)
_FULLWIDTH_TABLE = str.maketrans(_FULLWIDTH_SRC, _FULLWIDTH_DST)

# 常见繁体 → 简体（v1 精选基线，覆盖客服高频词）
_TRADITIONAL_TO_SIMPLIFIED = {
    "買": "买", "賣": "卖", "個": "个", "們": "们", "讓": "让", "這": "这",
    "對": "对", "還": "还", "來": "来", "體": "体", "係": "系", "訂": "单",
    "單": "单", "費": "费", "貨": "货", "錢": "钱", "優": "优", "問": "问",
    "題": "题", "處": "理", "項": "项", "務": "务", "售": "售", "後": "后",
    "開": "开", "關": "关", "於": "于", "與": "与", "為": "为", "麼": "么",
    "嗎": "吗", "沒": "没", "請": "请", "詢": "询", "訴": "诉", "報": "报",
    "號": "号", "碼": "码", "驗": "验", "證": "证", "產": "产", "價": "价",
    "賠": "赔", "償": "偿", "發": "发", "現": "现", "額": "额", "運": "运",
    "輸": "输", "週": "周", "賬": "账", "戶": "户", "遞": "递", "電": "电",
    "話": "话", "機": "机", "庫": "库", "標": "标", "識": "识", "總": "总",
    "結": "结", "帳": "账", "點": "点", "匯": "汇", "舉": "举", "註": "注",
    "滿": "满", "意": "意", "覆": "复", "雑": "杂",
}
_TRADITIONAL_TABLE = str.maketrans(_TRADITIONAL_TO_SIMPLIFIED)

# 形近字/常见错别字纠错（v1 基线；在繁简转换之后对简体文本生效）
_LOOKALIKE_CORRECTIONS = {
    "资询": "咨询",
    "投拆": "投诉",
    "收后": "售后",
    "支术": "支持",
    "帐号": "账号",
}

# 归一化第二步：去除空白与一切符号/表情（\W 在 re.UNICODE 下含全角标点与 emoji）
_PUNCTUATION_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize(text: str) -> str:
    """归一化：全角→半角 → 去空格/符号 → 繁简转换 → 形近字纠错。"""
    result = text.translate(_FULLWIDTH_TABLE)
    result = _PUNCTUATION_RE.sub("", result)
    result = result.translate(_TRADITIONAL_TABLE)
    for wrong, right in _LOOKALIKE_CORRECTIONS.items():
        if wrong in result:
            result = result.replace(wrong, right)
    return result
