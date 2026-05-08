"""文本预处理模块：在章节正则匹配之前对原文进行标准化处理。"""
import re
import unicodedata


# 编码检测与转换

def detect_and_convert_encoding(raw_bytes: bytes) -> str:
    """检测并转换文件编码为 UTF-8。"""
    try:
        return raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        pass

    try:
        return raw_bytes.decode('gb18030')
    except UnicodeDecodeError:
        pass

    try:
        return raw_bytes.decode('big5')
    except UnicodeDecodeError:
        pass

    return raw_bytes.decode('latin-1', errors='replace')


def normalize_line_endings(text: str) -> str:
    """统一换行符为 Unix 格式 (LF)。"""
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    return text


# 中文数字映射

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
    """将中文数字字符串转换为整数。"""
    cn = cn.strip()
    if not cn:
        return 0

    if cn.isdigit():
        return int(cn)

    result = 0
    unit = 1
    tmp = 0

    if cn[0] in ("十", "拾"):
        cn = "一" + cn

    for ch in reversed(cn):
        if ch in _CN_UNIT:
            u = _CN_UNIT[ch]
            if u >= 10000:
                result += tmp * u
                tmp = 0
                unit = 1
            else:
                unit = u
        elif ch in _CN_BASIC:
            tmp += _CN_BASIC[ch] * unit
            unit = 1

    result += tmp
    return result


_CN_NUM_PATTERN = re.compile(
    r"(第\s*)([零〇一壹二贰两三叁四肆五伍六陆七柒八捌九玖十拾百佰千仟万亿]+)(\s*[章节回篇])"
)


def convert_cn_chapter_numbers(text: str) -> str:
    """将章节标题中的中文数字替换为阿拉伯数字。"""
    def _replace(m: re.Match) -> str:
        prefix = m.group(1)
        cn_num = m.group(2)
        suffix = m.group(3)
        try:
            arabic = _cn_to_int(cn_num)
            return f"{prefix}{arabic}{suffix}"
        except Exception:
            return m.group(0)

    return _CN_NUM_PATTERN.sub(_replace, text)


# 去广告 / 水印

_AD_LINE_PATTERNS = [
    re.compile(r"^\s*本书来自.{0,30}\s*$"),
    re.compile(r"^\s*本文由.{0,30}(?:提供|发布|整理)\s*$"),
    re.compile(r"^\s*(?:www|http|https)://[^\s]{3,60}\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:请到|欢迎来到|推荐|收藏|投票|打赏|订阅).{0,30}\s*$"),
    re.compile(r"^\s*请记住.*?(?:网站|网址|域名).{0,30}\s*$", re.IGNORECASE),
    re.compile(r"^\s*更多.{0,5}小说.{0,10}(?:尽在|下载).{0,30}\s*$"),
    re.compile(r"^\s*精校小说.{0,30}\s*$"),
    re.compile(r"^\s*[\-=_\*]{5,}\s*$"),
    re.compile(r"^\s*(?:全文完|完本|正文完|大结局)\s*$"),
    re.compile(r"^\s*\(?\s*(?:笔趣阁|起点|晋江|纵横|17k|六九|免费|全本|速读谷|看书|小说网|知轩藏书).{0,20}\s*\)?\s*$"),
    re.compile(r"^\s*(?:求.{0,5}(?:月票|推荐票|收藏|订阅|打赏)|跪求|求支持).{0,20}\s*$"),
    re.compile(r"^\s*(?:无弹窗|手机阅读|客户端|APP).{0,20}\s*$"),
    re.compile(r"^\s*[（\(]?本章完[）\)]?\s*$"),
    re.compile(r"^\s*更新不易.{0,30}\s*$"),
    re.compile(r"^\s*(?:扫码|关注|微信|公众号|QQ|群).{0,30}\s*$"),
    re.compile(r"^\s*添加.*?(?:微信|QQ|群|公众号).{0,30}\s*$"),
    re.compile(r"^\s*[锞晞囂鐜讚魐鏴灚矗薋鬻龘鵺麣鸂鼱].{0,50}\s*$"),
    re.compile(r"^\s*[★☆●○◆◇■□▲△▼▽◐◑◑▓▒░]{3,}\s*$"),
]

_AD_INLINE_PATTERNS = [
    r"[（\(]请记住.*?(?:网站|网址|域名).*?[）\)]",
    r"请记住.*?(?:网站|网址|域名)[^。\n]*",
    r"本文由.{0,20}(?:提供|发布|整理)[^。\n]*",
    r"更新不易.{0,30}(?:章节|分享|速读谷|rg)[^。\n]*",
    r"[（\(]?本章完[）\)]?",
    r"[（\(]ps：[^）\)]*[）\)]",
    r"[（\(]PS：[^）\)]*[）\)]",
    r"ps：求[^。\n]*",
    r"PS：求[^。\n]*",
    r"【[^】]*(?:笔趣阁|小说网|看书|阅读|知轩藏书|一秒记住|记住|秒记住)[^】]*】",
    r"[（\(][^）\)]*(?:笔趣阁|小说网|看书|阅读|知轩藏书)[^）\)]*[）\)]",
    r"[（\(][^）\)]*(?:提醒您|请注意|温馨提示)[^）\)]*[）\)]",
    r"扫码关注.{0,20}",
    r"添加.{0,5}(?:微信|QQ|群|公众号).{0,20}",
    r"(?:微信|公众号|QQ群)[^。\n]*(?:关注|添加|扫码)",
    r"[锞晞囂鐜讚魐鏴灚矗薋鬻龘鵺麣鸂鼱]+",
]


def remove_duplicate_ads(text: str, min_length: int = 20) -> str:
    """检测并删除重复的广告段落。"""
    paragraphs = text.split("\n\n")
    seen = {}
    result = []

    for para in paragraphs:
        para_stripped = para.strip()

        if not para_stripped:
            result.append(para)
            continue

        if len(para_stripped) < min_length:
            result.append(para)
            continue

        if para_stripped in seen:
            continue

        seen[para_stripped] = True
        result.append(para)

    return "\n\n".join(result)


def remove_ad_lines(text: str) -> str:
    """逐行过滤广告/水印行，并清理行内广告。

    注意：不删除空白行，空白行由 normalize_whitespace 统一处理。
    """
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        # 过滤广告行
        if any(pat.match(line) for pat in _AD_LINE_PATTERNS):
            continue

        # 清理行内广告
        for pattern in _AD_INLINE_PATTERNS:
            line = re.sub(pattern, '', line, flags=re.IGNORECASE)

        # 清理行内多余空白，但保留空行
        line = line.strip()
        clean_lines.append(line)

    return "\n".join(clean_lines)


# 编码 / 空白归一化

def normalize_whitespace(text: str) -> str:
    """统一全角空格、多余空行。"""
    text = text.replace("　", " ")
    lines = [line.strip() for line in text.split("\n")]
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
    """NFC 归一化。"""
    return unicodedata.normalize("NFC", text)


# 主入口

def preprocess(raw_bytes: bytes) -> str:
    """对原始小说文本执行完整预处理流水线。"""
    text = detect_and_convert_encoding(raw_bytes)
    text = normalize_line_endings(text)
    text = normalize_unicode(text)
    text = remove_ad_lines(text)
    text = remove_duplicate_ads(text)
    text = convert_cn_chapter_numbers(text)
    text = normalize_whitespace(text)
    return text


def preprocess_text(text: str) -> str:
    """对已解码文本执行预处理。"""
    text = normalize_line_endings(text)
    text = normalize_unicode(text)
    text = remove_ad_lines(text)
    text = remove_duplicate_ads(text)
    text = convert_cn_chapter_numbers(text)
    text = normalize_whitespace(text)
    return text