"""文本预处理模块：在章节正则匹配之前对原文进行标准化处理。

处理流程：
    原文 → 编码归一化 → 去广告水印 → 中文数字 → 阿拉伯数字 → 空白清理
"""
import re
import unicodedata

# ──────────────────────────────────────────────
# 中文数字映射
# ──────────────────────────────────────────────

_CN_BASIC = {
    "零": 0, "〇": 0,
    "一": 1, "壹": 1,
    "二": 2, "贰": 2, "两": 2,
    "三": 3, "叁": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陆": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}

_CN_UNIT = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "万": 10000,
    "亿": 100000000,
}


def _cn_to_int(cn: str) -> int:
    """将中文数字字符串转换为整数，支持到亿级。"""
    cn = cn.strip()
    if not cn:
        return 0

    # 纯阿拉伯数字直接返回
    if cn.isdigit():
        return int(cn)

    result = 0
    unit = 1
    tmp = 0

    # 处理以"十"开头的情形，如"十二"= 12
    if cn[0] in ("十", "拾"):
        cn = "一" + cn

    for ch in reversed(cn):
        if ch in _CN_UNIT:
            u = _CN_UNIT[ch]
            if u >= 10000:
                # 万/亿 作为段分隔
                result += tmp * u
                tmp = 0
                unit = 1
            else:
                unit = u
        elif ch in _CN_BASIC:
            tmp += _CN_BASIC[ch] * unit
            unit = 1
        # 忽略无法识别的字符

    result += tmp
    return result


# 匹配章节标题中的中文数字部分（贪婪，最多匹配 8 个汉字）
_CN_NUM_PATTERN = re.compile(
    r"(第\s*)([零〇一壹二贰两三叁四肆五伍六陆七柒八捌九玖十拾百佰千仟万亿]+)(\s*[章节回卷篇])"
)


def convert_cn_chapter_numbers(text: str) -> str:
    """将章节标题中的中文数字替换为阿拉伯数字。

    例：「第一百二十三章」→「第123章」
    """
    def _replace(m: re.Match) -> str:
        prefix = m.group(1)
        cn_num = m.group(2)
        suffix = m.group(3)
        try:
            arabic = _cn_to_int(cn_num)
            return f"{prefix}{arabic}{suffix}"
        except Exception:
            return m.group(0)  # 转换失败保留原文

    return _CN_NUM_PATTERN.sub(_replace, text)


# ──────────────────────────────────────────────
# 去广告 / 水印
# ──────────────────────────────────────────────

# 常见网文广告行特征（整行匹配）
_AD_LINE_PATTERNS = [
    re.compile(r"^\s*本书来自.{0,30}\s*$"),
    re.compile(r"^\s*(?:www|http|https)[^\s]{3,60}\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:请到|欢迎来到|推荐|收藏|投票|打赏|订阅).{0,30}\s*$"),
    re.compile(r"^\s*[\-=_\*]{5,}\s*$"),          # 分隔线
    re.compile(r"^\s*(?:全文完|完本|正文完|大结局)\s*$"),
    re.compile(r"^\s*\(?\s*(?:笔趣阁|起点|晋江|纵横|17k|六九|免费|全本).{0,20}\s*\)?\s*$"),
]


def remove_ad_lines(text: str) -> str:
    """逐行过滤广告/水印行。"""
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        if any(pat.match(line) for pat in _AD_LINE_PATTERNS):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines)


# ──────────────────────────────────────────────
# 编码 / 空白归一化
# ──────────────────────────────────────────────

def normalize_whitespace(text: str) -> str:
    """统一全角空格、多余空行。"""
    # 全角空格 → 半角空格
    text = text.replace("\u3000", " ")
    # 去除每行行首行尾多余空白
    lines = [line.strip() for line in text.split("\n")]
    # 压缩连续空行（最多保留 1 行）
    result = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return "\n".join(result)


def normalize_unicode(text: str) -> str:
    """NFC 归一化，统一处理繁简混用、异体字等编码问题。"""
    return unicodedata.normalize("NFC", text)


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def preprocess(text: str) -> str:
    """对原始小说文本执行完整预处理流水线。

    Args:
        text: 原始文本内容

    Returns:
        str: 标准化后的文本，可直接送入章节正则匹配
    """
    text = normalize_unicode(text)
    text = remove_ad_lines(text)
    text = convert_cn_chapter_numbers(text)
    text = normalize_whitespace(text)
    return text
