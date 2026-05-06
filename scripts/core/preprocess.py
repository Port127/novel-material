"""文本预处理模块：在章节正则匹配之前对原文进行标准化处理。

处理流程：
    原文 → 编码归一化 → 去广告水印 → 中文数字 → 阿拉伯数字 → 空白清理
"""
import re
import unicodedata


# ──────────────────────────────────────────────
# 编码检测与转换
# ──────────────────────────────────────────────

def detect_and_convert_encoding(raw_bytes: bytes) -> str:
    """检测并转换文件编码为 UTF-8。

    支持的编码：
    - UTF-8 (默认)
    - GBK/GB18030 (常见中文编码)
    - Big5 (繁体中文)
    - Latin-1 (西欧编码)

    Args:
        raw_bytes: 原始文件字节

    Returns:
        str: UTF-8 编码的文本
    """
    # 尝试 UTF-8
    try:
        return raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # 尝试 GB18030（GBK 的超集，覆盖更广）
    try:
        return raw_bytes.decode('gb18030')
    except UnicodeDecodeError:
        pass

    # 尝试 Big5
    try:
        return raw_bytes.decode('big5')
    except UnicodeDecodeError:
        pass

    # 最后尝试 Latin-1（不会失败）
    return raw_bytes.decode('latin-1', errors='replace')


def normalize_line_endings(text: str) -> str:
    """统一换行符为 Unix 格式 (LF)。"""
    # CRLF (Windows) → LF
    text = text.replace('\r\n', '\n')
    # CR (Mac old) → LF
    text = text.replace('\r', '\n')
    return text


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


# 匹配章节标题中的中文数字部分
# 注意：只转换章节/节/回/篇，不转换卷/部（通常是分卷/分部标题）
_CN_NUM_PATTERN = re.compile(
    r"(第\s*)([零〇一壹二贰两三叁四肆五伍六陆七柒八捌九玖十拾百佰千仟万亿]+)(\s*[章节回篇])"
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

# 整行广告模式（删除整行）
_AD_LINE_PATTERNS = [
    # 网站提示/站点水印（必须以www/http开头且整行只有URL或简短说明）
    re.compile(r"^\s*本书来自.{0,30}\s*$"),
    re.compile(r"^\s*本文由.{0,30}(?:提供|发布|整理)\s*$"),
    re.compile(r"^\s*(?:www|http|https)://[^\s]{3,60}\s*$", re.IGNORECASE),  # 仅匹配纯URL行
    re.compile(r"^\s*(?:请到|欢迎来到|推荐|收藏|投票|打赏|订阅).{0,30}\s*$"),
    re.compile(r"^\s*请记住.*?(?:网站|网址|域名).{0,30}\s*$", re.IGNORECASE),
    re.compile(r"^\s*更多.{0,5}小说.{0,10}(?:尽在|下载).{0,30}\s*$"),  # 知轩藏书等站点水印
    re.compile(r"^\s*精校小说.{0,30}\s*$"),
    # 分隔线
    re.compile(r"^\s*[\-=_\*]{5,}\s*$"),
    # 完本标记
    re.compile(r"^\s*(?:全文完|完本|正文完|大结局)\s*$"),
    # 站点名称行（单独出现）
    re.compile(r"^\s*\(?\s*(?:笔趣阁|起点|晋江|纵横|17k|六九|免费|全本|速读谷|看书|小说网|知轩藏书).{0,20}\s*\)?\s*$"),
    # 求票/求支持
    re.compile(r"^\s*(?:求.{0,5}(?:月票|推荐票|收藏|订阅|打赏)|跪求|求支持).{0,20}\s*$"),
    # 无弹窗/手机阅读提示
    re.compile(r"^\s*(?:无弹窗|手机阅读|客户端|APP).{0,20}\s*$"),
    # 本章完标记
    re.compile(r"^\s*[（\(]?本章完[）\)]?\s*$"),
    # 更新提示
    re.compile(r"^\s*更新不易.{0,30}\s*$"),
    # 推广链接/二维码
    re.compile(r"^\s*(?:扫码|关注|微信|公众号|QQ|群).{0,30}\s*$"),
    re.compile(r"^\s*添加.*?(?:微信|QQ|群|公众号).{0,30}\s*$"),
    # 乱码广告（检测非正常字符高密度行）
    re.compile(r"^\s*[锞晞囂鐜讚魐鏴灚矗薋鬻龘鵺麣鸂鼱].{0,50}\s*$"),
    # 纯符号行
    re.compile(r"^\s*[★☆●○◆◇■□▲△▼▽◐◑◑▓▒░]{3,}\s*$"),
]

# 行内广告模式（删除匹配内容，保留行）
_AD_INLINE_PATTERNS = [
    # 网站提示
    r"[（\(]请记住.*?(?:网站|网址|域名).*?[）\)]",
    r"请记住.*?(?:网站|网址|域名)[^。\n]*",
    # 本文由xxx提供
    r"本文由.{0,20}(?:提供|发布|整理)[^。\n]*",
    # 速读谷等站点广告
    r"更新不易.{0,30}(?:章节|分享|速读谷|rg)[^。\n]*",
    # 本章完标记
    r"[（\(]?本章完[）\)]?",
    # PS注释（含求票）
    r"[（\(]ps：[^）\)]*[）\)]",
    r"[（\(]PS：[^）\)]*[）\)]",
    r"ps：求[^。\n]*",
    r"PS：求[^。\n]*",
    # 站点水印（方括号/圆括号包裹）
    r"【[^】]*(?:笔趣阁|小说网|看书|阅读|知轩藏书|一秒记住|记住|秒记住)[^】]*】",
    r"[（\(][^）\)]*(?:笔趣阁|小说网|看书|阅读|知轩藏书)[^）\)]*[）\)]",
    # 网站提醒（宽泛匹配）
    r"[（\(][^）\)]*(?:提醒您|请注意|温馨提示)[^）\)]*[）\)]",
    # 推广链接
    r"扫码关注.{0,20}",
    r"添加.{0,5}(?:微信|QQ|群|公众号).{0,20}",
    r"(?:微信|公众号|QQ群)[^。\n]*(?:关注|添加|扫码)",
    # 乱码广告（行内）
    r"[锞晞囂鐜讚魐鏴灚矗薋鬻龘鵺麣鸂鼱]+",
]


def remove_duplicate_ads(text: str, min_length: int = 20) -> str:
    """检测并删除重复的广告段落。

    Args:
        text: 输入文本
        min_length: 最小段落长度（低于此长度不检测，避免误删短句）

    Returns:
        清理后的文本
    """
    paragraphs = text.split("\n\n")
    seen = {}
    result = []

    for para in paragraphs:
        para_stripped = para.strip()

        # 空段落保留
        if not para_stripped:
            result.append(para)
            continue

        # 短段落不检测重复
        if len(para_stripped) < min_length:
            result.append(para)
            continue

        # 检测重复
        if para_stripped in seen:
            # 重复段落，跳过（广告通常会在每章重复出现）
            continue

        seen[para_stripped] = True
        result.append(para)

    return "\n\n".join(result)


def remove_ad_lines(text: str) -> str:
    """逐行过滤广告/水印行，并清理行内广告。"""
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        # 整行广告检测
        if any(pat.match(line) for pat in _AD_LINE_PATTERNS):
            continue

        # 行内广告清理
        for pattern in _AD_INLINE_PATTERNS:
            line = re.sub(pattern, '', line, flags=re.IGNORECASE)

        # 清理后如果行变为空白，跳过
        if not line.strip():
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

def preprocess(raw_bytes: bytes) -> str:
    """对原始小说文本执行完整预处理流水线。

    Args:
        raw_bytes: 原始文件字节（自动检测编码）

    Returns:
        str: 标准化后的文本，可直接送入章节正则匹配
    """
    # 编码检测与转换
    text = detect_and_convert_encoding(raw_bytes)
    # 换行符统一
    text = normalize_line_endings(text)
    # Unicode 归一化
    text = normalize_unicode(text)
    # 去广告
    text = remove_ad_lines(text)
    # 删除重复广告段落
    text = remove_duplicate_ads(text)
    # 中文数字转换
    text = convert_cn_chapter_numbers(text)
    # 空白清理
    text = normalize_whitespace(text)
    return text


def preprocess_text(text: str) -> str:
    """对已解码文本执行预处理（供已读取的文本使用）。

    Args:
        text: 已解码的文本内容

    Returns:
        str: 标准化后的文本
    """
    text = normalize_line_endings(text)
    text = normalize_unicode(text)
    text = remove_ad_lines(text)
    text = remove_duplicate_ads(text)
    text = convert_cn_chapter_numbers(text)
    text = normalize_whitespace(text)
    return text
