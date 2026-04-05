#!/usr/bin/env python3
"""
source_format.py — 小说原文格式清洗脚本

固化核心清洗逻辑，避免每次由 agent 动态生成。
覆盖：章节分析、章节名标准化、繁简转换、引号修复、广告清理、格式统一。

用法:
    python scripts/source_format.py <input_file> <output_file> <report_file>

输出:
    - output_file: 清洗后的文本
    - report_file: YAML 格式的清洗报告（符合 format-report.schema.yaml）
"""

import argparse
import re
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

try:
    from opencc import OpenCC
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False


# ── 章节标题模式 ──────────────────────────────────────────────

CHAPTER_PATTERNS = [
    # 第X章 / 第X回 / 第X节（中文数字或阿拉伯数字）
    re.compile(
        r'^[\s　]*(第\s*[零一二三四五六七八九十百千万\d]+\s*[章回节卷部篇集])\s*(.*?)[\s　]*$',
        re.MULTILINE,
    ),
    # Chapter X / CHAPTER X
    re.compile(r'^[\s　]*(Chapter\s+\d+)\s*(.*?)[\s　]*$', re.MULTILINE | re.IGNORECASE),
    # 纯数字章节号（行首独立数字，如 "001" "1."）
    re.compile(r'^[\s　]*(\d{1,4})[.\s、．]\s*(.*?)[\s　]*$', re.MULTILINE),
]

CN_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10, '百': 100, '千': 1000, '万': 10000,
    '〇': 0, '两': 2,
}


def cn_to_int(cn: str) -> int | None:
    """中文数字 → 整数。失败返回 None。"""
    cn = cn.strip()
    if cn.isdigit():
        return int(cn)
    total = 0
    current = 0
    for ch in cn:
        val = CN_NUM_MAP.get(ch)
        if val is None:
            return None
        if val >= 10:
            current = current or 1
            if val >= 10000:
                total = (total + current) * val
                current = 0
            else:
                current *= val
                total += current
                current = 0
        else:
            current = current * 10 + val
    return total + current


# ── 广告/干扰模式 ────────────────────────────────────────────

AD_PATTERNS = [
    re.compile(r'.*本[书文]来自.{0,20}[网站].*', re.IGNORECASE),
    re.compile(r'.*更多好书请访问.*'),
    re.compile(r'.*[wW]{3}\..+\.(com|net|org|cn|cc).*'),
    re.compile(r'.*https?://\S+.*'),
    re.compile(r'.*求[票订].{0,10}[票阅].*'),
    re.compile(r'.*[推荐|收藏|点击|书签].{0,5}一下.*'),
    re.compile(r'.*手机用户请到.+阅读.*'),
    re.compile(r'.*最新章节请到.+阅读.*'),
    re.compile(r'.*喜欢本书请.{0,10}推荐.*'),
    re.compile(r'.*本章未完.*点击下一页.*'),
    re.compile(r'.*正在手打中.*请稍等.*'),
    re.compile(r'^\s*[─━═—_\-~·.。]{10,}\s*$'),  # 重复分隔符行
]


def is_ad_line(line: str) -> bool:
    return any(p.match(line) for p in AD_PATTERNS)


# ── 引号修复 ─────────────────────────────────────────────────

def fix_quotes(text: str) -> tuple[str, int]:
    """修复引号问题，返回 (修复后文本, 修复处数)。"""
    count = 0

    # 双重引号 → 单引号
    for doubled in ['""', '""', '""', '「「', '」」']:
        c = text.count(doubled)
        if c > 0:
            text = text.replace(doubled, doubled[0])
            count += c

    # 直引号 → 弯引号（简单启发：奇数位为左引号，偶数位为右引号）
    parts = text.split('"')
    if len(parts) > 1:
        rebuilt = []
        for i, part in enumerate(parts):
            rebuilt.append(part)
            if i < len(parts) - 1:
                rebuilt.append('\u201c' if i % 2 == 0 else '\u201d')
                count += 1
        text = ''.join(rebuilt)

    return text, count


# ── 标点统一 ─────────────────────────────────────────────────

def normalize_punctuation(text: str) -> tuple[str, int]:
    """统一省略号、破折号等标点，返回 (修复后文本, 修复处数)。"""
    count = 0

    # 省略号：各种变体 → ……
    for pattern in [r'\.{3,}', r'。{3,}', r'…{1,3}(?!…)', r'\.\.']:
        matches = len(re.findall(pattern, text))
        if matches:
            text = re.sub(pattern, '……', text)
            count += matches

    # 破折号：各种变体 → ——
    for pattern in [r'-{2,}', r'—{1}(?!—)', r'–{1,}', r'－{2,}']:
        matches = len(re.findall(pattern, text))
        if matches:
            text = re.sub(pattern, '——', text)
            count += matches

    return text, count


# ── 格式统一 ─────────────────────────────────────────────────

def normalize_whitespace(text: str) -> tuple[str, int]:
    """段落间距、行首行尾空白标准化。"""
    count = 0
    lines = text.split('\n')
    result = []
    prev_blank = False

    for line in lines:
        stripped = line.rstrip()
        if stripped != line:
            count += 1
        line = stripped

        is_blank = len(line.strip()) == 0
        if is_blank:
            if prev_blank:
                count += 1
                continue
            prev_blank = True
            result.append('')
        else:
            prev_blank = False
            clean = line.lstrip('\u3000').lstrip(' ')
            if clean and clean != line:
                count += 1
                line = '　' + clean  # 保留一个全角空格缩进
            result.append(line)

    return '\n'.join(result), count


# ── 乱码检测 ─────────────────────────────────────────────────

GARBLED_PATTERN = re.compile(r'[\ufffd\ufffe\ufeff]|[\x00-\x08\x0b\x0c\x0e-\x1f]')


def clean_garbled(text: str) -> tuple[str, int]:
    matches = len(GARBLED_PATTERN.findall(text))
    if matches:
        text = GARBLED_PATTERN.sub('', text)
    return text, matches


# ── 主流程 ───────────────────────────────────────────────────

def analyze_chapters(text: str) -> dict:
    """分析章节结构，返回章节列表和问题。"""
    chapters = []

    for pattern in CHAPTER_PATTERNS:
        for m in pattern.finditer(text):
            prefix = m.group(1).strip()
            title = m.group(2).strip() if m.lastindex >= 2 else ''
            pos = m.start()

            # 提取章节号
            num_match = re.search(r'[零一二三四五六七八九十百千万\d]+', prefix)
            if num_match:
                num = cn_to_int(num_match.group())
            else:
                num = None

            if num is not None:
                chapters.append({
                    'num': num,
                    'prefix': prefix,
                    'title': title,
                    'pos': pos,
                    'line': text[:pos].count('\n') + 1,
                })

        if chapters:
            break  # 用第一个匹配到的模式

    chapters.sort(key=lambda c: c['pos'])

    # 去重（相同章节号取第一个）
    seen = set()
    deduped = []
    for ch in chapters:
        if ch['num'] not in seen:
            seen.add(ch['num'])
            deduped.append(ch)
        # 重复的保留记录但标记
    chapters = deduped

    # 计算每章字数
    for i, ch in enumerate(chapters):
        if i + 1 < len(chapters):
            ch['char_count'] = chapters[i + 1]['pos'] - ch['pos']
        else:
            ch['char_count'] = len(text) - ch['pos']

    # 缺失检测
    if chapters:
        nums = [c['num'] for c in chapters]
        expected = set(range(min(nums), max(nums) + 1))
        missing = sorted(expected - set(nums))
    else:
        missing = []

    # 短章检测
    short = [c for c in chapters if c['char_count'] < 200]

    return {
        'chapters': chapters,
        'total': len(chapters),
        'missing': missing,
        'short': short,
    }


def normalize_chapter_titles(text: str, chapters: list[dict]) -> tuple[str, int]:
    """标准化章节标题，返回 (修复后文本, 标准化数)。"""
    if not chapters:
        return text, 0

    count = 0
    replacements = []

    for ch in chapters:
        num = ch['num']
        title = ch['title']
        old_line_match = re.search(
            re.escape(ch['prefix']) + r'\s*' + re.escape(title),
            text[ch['pos']:ch['pos'] + 200],
        )
        if old_line_match:
            old = old_line_match.group()
            new = f'第{num}章 {title}'.rstrip()
            if old != new:
                replacements.append((ch['pos'] + old_line_match.start(), old, new))
                count += 1

    # 从后往前替换，避免位移
    for pos, old, new in reversed(replacements):
        idx = text.find(old, pos)
        if idx >= 0:
            text = text[:idx] + new + text[idx + len(old):]

    return text, count


def convert_traditional_to_simplified(text: str) -> tuple[str, int]:
    """繁→简转换。"""
    if not HAS_OPENCC:
        return text, 0

    cc = OpenCC('t2s')
    converted = cc.convert(text)

    diff_count = sum(1 for a, b in zip(text, converted) if a != b)
    return converted, diff_count


def remove_ads(text: str) -> tuple[str, int]:
    """移除广告行。"""
    lines = text.split('\n')
    cleaned = []
    count = 0
    for line in lines:
        if is_ad_line(line):
            count += 1
        else:
            cleaned.append(line)
    return '\n'.join(cleaned), count


def format_source(input_path: str, output_path: str, report_path: str) -> dict:
    """主入口：执行全部清洗步骤。"""
    text = Path(input_path).read_text(encoding='utf-8')
    original_chars = len(text)
    original_lines = text.count('\n') + 1
    modified_lines = 0

    stats = {}

    # 1. 章节分析
    ch_info = analyze_chapters(text)
    chapters = ch_info['chapters']

    # 2. 章节名标准化
    text, n = normalize_chapter_titles(text, chapters)
    stats['chapter_title_normalized'] = n
    modified_lines += n

    # 3. 繁简转换
    text, n = convert_traditional_to_simplified(text)
    stats['traditional_to_simplified'] = n

    # 4. 引号修复
    text, n = fix_quotes(text)
    stats['quote_fixed'] = n
    modified_lines += n

    # 5. 广告清理
    text, n = remove_ads(text)
    stats['ads_removed'] = n

    # 6. 乱码清理
    text, n = clean_garbled(text)
    stats['garbled_cleaned'] = n

    # 7. 标点统一
    text, n = normalize_punctuation(text)
    stats['punctuation_fixed'] = n
    modified_lines += n

    # 8. 空白格式统一
    text, n = normalize_whitespace(text)
    stats['whitespace_fixed'] = n
    modified_lines += n

    cleaned_chars = len(text)

    # 写清洗后文本
    Path(output_path).write_text(text, encoding='utf-8')

    # 构建报告
    suspicious = []
    for m in ch_info['missing']:
        suspicious.append({
            'chapter': m,
            'issue': f'章节缺失，章节号 {m} 未找到',
            'severity': 'high',
        })
    for s in ch_info['short']:
        suspicious.append({
            'chapter': s['num'],
            'issue': f'章节字数仅 {s["char_count"]} 字，疑似截断',
            'severity': 'medium',
        })

    # 检测重复（简化：只看标题重复）
    title_counts = Counter(
        f'{c["prefix"]} {c["title"]}' for c in chapters
    )
    duplicates = []
    for title, cnt in title_counts.items():
        if cnt > 1:
            dup_chapters = [c for c in chapters if f'{c["prefix"]} {c["title"]}' == title]
            for d in dup_chapters[1:]:
                duplicates.append({
                    'chapter': d['num'],
                    'duplicate_of': dup_chapters[0]['num'],
                    'similarity': 1.0,
                })

    report = {
        'formatted_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'chapters': {
            'total_detected': ch_info['total'],
            'title_pattern': '第{N}章 {name}',
            'missing': ch_info['missing'],
            'duplicates': duplicates,
            'short_chapters': [
                {'chapter': s['num'], 'char_count': s['char_count'], 'note': '疑似截断'}
                for s in ch_info['short']
            ],
        },
        'fixes': stats,
        'suspicious': suspicious,
        'diff_summary': {
            'original_chars': original_chars,
            'cleaned_chars': cleaned_chars,
            'removed_chars': original_chars - cleaned_chars,
            'modified_lines': modified_lines,
        },
    }

    # 写 YAML 报告（手动序列化，避免依赖 pyyaml）
    report_text = dump_yaml(report)
    Path(report_path).write_text(report_text, encoding='utf-8')

    return report


def dump_yaml(obj, indent=0) -> str:
    """轻量 YAML 序列化（仅支持 dict/list/scalar）。"""
    prefix = '  ' * indent
    lines = []

    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, (dict,)):
                lines.append(f'{prefix}{key}:')
                lines.append(dump_yaml(val, indent + 1))
            elif isinstance(val, list):
                lines.append(f'{prefix}{key}:')
                if not val:
                    lines[-1] = f'{prefix}{key}: []'
                elif isinstance(val[0], dict):
                    for item in val:
                        lines.append(f'{prefix}  -')
                        for k, v in item.items():
                            lines.append(f'{prefix}    {k}: {_scalar(v)}')
                else:
                    lines[-1] = f'{prefix}{key}: [{", ".join(str(v) for v in val)}]'
            else:
                lines.append(f'{prefix}{key}: {_scalar(val)}')
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                lines.append(f'{prefix}-')
                for k, v in item.items():
                    lines.append(f'{prefix}  {k}: {_scalar(v)}')
            else:
                lines.append(f'{prefix}- {_scalar(item)}')

    return '\n'.join(lines)


def _scalar(val) -> str:
    if isinstance(val, str):
        if any(c in val for c in ':#{}[],"\''):
            return f'"{val}"'
        return f'"{val}"' if not val else val
    if isinstance(val, bool):
        return 'true' if val else 'false'
    if val is None:
        return 'null'
    return str(val)


def main():
    parser = argparse.ArgumentParser(description='小说原文格式清洗')
    parser.add_argument('input', help='输入文件路径')
    parser.add_argument('output', help='输出文件路径')
    parser.add_argument('report', help='报告文件路径 (YAML)')
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f'ERROR: 输入文件不存在: {args.input}', file=sys.stderr)
        sys.exit(1)

    report = format_source(args.input, args.output, args.report)

    # 输出摘要到 stdout（供 agent 读取）
    fixes = report['fixes']
    chapters = report['chapters']
    diff = report['diff_summary']
    suspicious = report['suspicious']

    print(f'chapters_total: {chapters["total_detected"]}')
    print(f'chapters_missing: {len(chapters["missing"])}')
    print(f'chapters_short: {len(chapters["short_chapters"])}')
    print(f'chapters_duplicate: {len(chapters["duplicates"])}')
    print(f'fix_t2s: {fixes.get("traditional_to_simplified", 0)}')
    print(f'fix_quotes: {fixes.get("quote_fixed", 0)}')
    print(f'fix_ads: {fixes.get("ads_removed", 0)}')
    print(f'fix_garbled: {fixes.get("garbled_cleaned", 0)}')
    print(f'fix_chapter_titles: {fixes.get("chapter_title_normalized", 0)}')
    print(f'fix_punctuation: {fixes.get("punctuation_fixed", 0)}')
    print(f'fix_whitespace: {fixes.get("whitespace_fixed", 0)}')
    print(f'original_chars: {diff["original_chars"]}')
    print(f'cleaned_chars: {diff["cleaned_chars"]}')
    print(f'removed_chars: {diff["removed_chars"]}')
    print(f'suspicious_count: {len(suspicious)}')

    if not HAS_OPENCC:
        print('WARNING: opencc 未安装，跳过繁简转换。pip install opencc-python-reimplemented')

    for s in suspicious:
        print(f'SUSPICIOUS: 第{s["chapter"]}章 - {s["issue"]} [{s["severity"]}]')


if __name__ == '__main__':
    main()
