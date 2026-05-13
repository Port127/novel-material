"""初始化标签数据：从 data/tags.yaml 导入到数据库。"""
import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

from novel_material.infra.yaml_io import load_yaml

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 未配置")

TAGS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "tags.yaml"


# 领域分配规则（关键词匹配）
TAG_DOMAIN_RULES = {
    "element": {
        # 玄幻专属
        "血脉": "xuanhuan", "御兽": "xuanhuan", "高武世界": "xuanhuan",
        "洞天": "xuanhuan", "秘境": "xuanhuan", "拍卖会": "xuanhuan",
        "天骄": "xuanhuan", "夺宝": "xuanhuan", "王朝争霸": "xuanhuan",

        # 仙侠专属
        "渡劫": "xianxia", "宗门": "xianxia", "修炼": "xianxia",
        "修仙": "xianxia", "炼丹": "xianxia", "炼器": "xianxia",
        "阵法": "xianxia", "飞升": "xianxia", "仙帝": "xianxia",
        "仙人": "xianxia", "道祖": "xianxia", "掌门": "xianxia",
        "长老": "xianxia", "宗主": "xianxia", "散修": "xianxia",
        "炼气修士": "xianxia", "筑基修士": "xianxia", "金丹修士": "xianxia",
        "元婴修士": "xianxia", "化神修士": "xianxia", "渡劫修士": "xianxia",
        "大乘修士": "xianxia", "内门弟子": "xianxia", "外门弟子": "xianxia",
        "杂役弟子": "xianxia", "执事": "xianxia", "护法": "xianxia",
        "供奉": "xianxia", "道门体系": "xianxia", "妖修体系": "xianxia",
        "鬼修体系": "xianxia", "魔道体系": "xianxia",

        # 都市专属
        "商战": "dushi", "娱乐圈": "dushi", "电竞": "dushi",
        "神豪": "dushi", "直播": "dushi", "职场": "dushi",
        "校园": "dushi", "都市生活": "dushi", "娱乐明星": "dushi",
        "商战职场": "dushi", "爱情婚姻": "dushi", "青春校园": "dushi",
        "都市神医": "dushi", "赘婿": "dushi",

        # 科幻专属
        "机甲": "kehuan", "星际": "kehuan", "丧尸": "kehuan",
        "末世": "kehuan", "末日": "kehuan", "进化变异": "kehuan",
        "人工智能": "kehuan", "赛博朋克": "kehuan", "星际文明": "kehuan",
        "时空穿梭": "kehuan", "超级科技": "kehuan", "硬科幻": "kehuan",
        "软科幻": "kehuan",

        # 奇幻专属（西方）
        "魔法": "qihuan", "骑士": "qihuan", "精灵": "qihuan",
        "龙": "qihuan", "兽人": "qihuan", "亡灵": "qihuan",
        "异世界": "qihuan", "剑与魔法": "qihuan", "现代魔法": "qihuan",
        "史诗奇幻": "qihuan", "神秘幻想": "qihuan", "历史神话": "qihuan",
        "另类幻想": "qihuan", "精灵宝可梦": "qihuan",

        # 悬疑灵异专属
        "诡异": "lingyi", "克苏鲁": "lingyi", "神秘复苏": "lingyi",
        "惊悚恐怖": "lingyi", "恐怖": "lingyi", "推理": "lingyi",
        "诡秘悬疑": "lingyi", "悬疑": "lingyi", "灵异神怪": "lingyi",
        "探险生存": "lingyi", "规则怪谈": "lingyi",

        # 武侠专属
        "江湖": "wuxia", "国术无双": "wuxia", "武侠": "wuxia",
        "传统武侠": "wuxia", "武侠幻想": "wuxia", "古武未来": "wuxia",

        # 游戏
        "网游": "game", "电竞": "game", "虚拟网游": "game",
        "游戏异界": "game", "游戏系统": "game", "游戏主播": "game",
        "电子竞技": "game",

        # 历史相关
        "架空历史": "history", "秦汉三国": "history", "上古先秦": "history",
        "两晋隋唐": "history", "五代十国": "history", "两宋元明": "history",
        "清史民国": "history", "外国历史": "history", "历史穿越": "history",
        "民间传说": "history",
    },
    "setting": {
        # 修真体系
        "修真体系": "cultivation", "炼气": "cultivation",
        "筑基": "cultivation", "金丹": "cultivation",
        "元婴": "cultivation", "化神": "cultivation",
        "渡劫": "cultivation", "大乘": "cultivation",
        "仙帝": "cultivation", "道祖": "cultivation",
        "武道体系": "cultivation", "剑道体系": "cultivation",
        "刀道体系": "cultivation", "枪道体系": "cultivation",
        "拳道体系": "cultivation", "佛门体系": "cultivation",
        "道门体系": "cultivation", "妖修体系": "cultivation",
        "鬼修体系": "cultivation", "魔道体系": "cultivation",
        "御兽体系": "cultivation", "炼丹体系": "cultivation",
        "炼器体系": "cultivation", "阵法体系": "cultivation",
        "符文体系": "cultivation", "巫术体系": "cultivation",
        "血脉体系": "cultivation", "命轮体系": "cultivation",
        "星力体系": "cultivation",

        # 魔法体系
        "魔法体系": "magic", "精灵": "magic", "龙族": "magic",
        "兽人": "magic", "亡灵": "magic", "骑士": "magic",
        "神格体系": "magic",

        # 科幻体系
        "科技体系": "kehuan", "基因体系": "kehuan",
        "异能体系": "kehuan", "魂力体系": "kehuan",
        "灵力体系": "kehuan", "真气体系": "kehuan",

        # 武侠体系
        "武道体系": "wuxia", "气血体系": "wuxia",
        "斗气体系": "wuxia",

        # 现代/无力量体系
        "城市": "modern", "学院": "modern",
        "村庄": "modern", "皇城": "modern",
        "拍卖行": "modern", "酒馆": "modern",
        "星球": "modern", "大陆": "modern",
        "森林": "modern", "沙漠": "modern",
        "海洋": "modern", "雪山": "modern",
        "火山": "modern", "沼泽": "modern",
        "草原": "modern", "峡谷": "modern",
        "岛屿": "modern", "洞府": "modern",
        "秘境": "modern", "异界": "modern",
        "仙界": "modern", "魔界": "modern",
        "妖界": "modern", "冥界": "modern",
        "战场": "modern", "遗迹": "modern",
        "墓地": "modern",

        # 势力组织（现代）
        "宗门": "modern", "门派": "modern", "家族": "modern",
        "皇朝": "modern", "王国": "modern", "部落": "modern",
        "学院": "modern", "佣兵团": "modern", "商会": "modern",
        "帮派": "modern", "教派": "modern", "刺客组织": "modern",
        "情报组织": "modern", "军队": "modern", "联盟": "modern",
        "公会": "modern", "地下组织": "modern", "守护组织": "modern",
        "反派势力": "modern", "中立组织": "modern", "神秘组织": "modern",
        "奴隶组织": "modern", "盗贼团": "modern", "佣兵组织": "modern",
        "赏金猎人": "modern", "情报贩子": "modern",
        "炼丹师协会": "modern", "炼器师协会": "modern",
        "阵法师协会": "modern", "御兽师协会": "modern",
        "冒险者协会": "modern",
    },
}


def resolve_domain(dimension: str, tag: str) -> str:
    """根据关键词匹配分配领域。"""
    # 1. 精确匹配
    if dimension in TAG_DOMAIN_RULES:
        if tag in TAG_DOMAIN_RULES[dimension]:
            return TAG_DOMAIN_RULES[dimension][tag]

    # 2. 包含关键词匹配
    if dimension in TAG_DOMAIN_RULES:
        for keyword, domain in TAG_DOMAIN_RULES[dimension].items():
            if keyword in tag or tag in keyword:
                return domain

    # 3. 默认为 common
    return "common"


def infer_dimension(tag: str) -> str:
    """根据标签内容推断维度。"""
    element_keywords = [
        "逆袭", "打脸", "装逼", "复仇", "成长", "羁绊", "牺牲", "背叛", "阴谋",
        "真相", "救赎", "宿命", "信念", "守护", "自由", "权力", "财富", "名誉",
        "身份", "血脉", "传承", "毁灭", "创造", "探索", "冒险", "寻宝", "战争",
        "和谈", "竞争", "比赛", "考核", "突破", "渡劫", "觉醒", "变身", "时空",
        "命运", "轮回", "因果", "缘分", "仇恨", "原谅", "团聚", "离别", "重生",
        "穿越", "系统", "金手指", "签到", "开局", "无敌", "废柴", "天才", "天骄",
        "召唤", "分身", "夺舍", "炼丹", "炼器", "阵法", "御兽", "美食", "音乐",
        "医术", "鉴宝", "直播", "国运", "末日", "末世", "丧尸", "修仙", "升级",
    ]

    setting_keywords = [
        "体系", "宗门", "门派", "家族", "皇朝", "王国", "部落", "学院", "佣兵团",
        "商会", "帮派", "教派", "军队", "联盟", "公会", "组织", "协会", "势力",
        "大陆", "星球", "城市", "村庄", "皇城", "江湖", "秘境", "洞天", "异界",
        "仙界", "魔界", "妖界", "冥界", "战场", "遗迹", "墓地", "森林", "沙漠",
        "海洋", "雪山", "火山", "沼泽", "草原", "峡谷", "岛屿", "洞府", "拍卖行",
    ]

    style_keywords = [
        "华丽", "朴素", "冷叙述", "诗化", "写实", "浪漫", "讽刺", "幽默", "诙谐",
        "庄重", "抒情", "白描", "细腻", "粗犷", "飘逸", "沉重", "轻快", "辛辣",
        "温婉", "硬朗", "阴郁", "清新", "诡谲", "热血燃", "虐心", "温馨", "治愈",
        "悲壮", "欢快", "悲凉", "恐怖", "紧张", "搞笑", "爽文", "快节奏", "慢节奏",
    ]

    structure_keywords = [
        "三幕式", "英雄之旅", "五幕式", "环形结构", "多线叙事", "单线叙事",
        "章回体", "单元剧", "编年体", "传记体", "日记体", "书信体", "嵌套叙事",
        "碎片化", "非线性", "第一人称", "第二人称", "第三人称", "顺叙", "倒叙",
        "插叙", "补叙", "预叙", "时空交错", "平行叙事", "时间跳跃", "闪回",
    ]

    chapter_keywords = [
        "开局困境", "悬念引入", "人物亮相", "世界观引入", "金手指觉醒",
        "初始冲突", "目标确立", "困境升级", "线索发现", "冲突升级", "关系发展",
        "能力提升", "信息揭示", "支线展开", "日常互动", "训练修炼", "任务执行",
        "探索发现", "情节反转", "目标切换", "立场转变", "盟友背叛", "真相揭露",
        "身份揭示", "重大损失", "意外事件", "终极对决", "生死抉择", "终极揭示",
    ]

    character_keywords = [
        "英雄", "导师", "伙伴", "反派", "信使", "变形者", "守门人", "小丑",
        "牺牲者", "救世主", "废柴", "天才", "逆袭者", "隐士", "复仇者", "守护者",
        "野心家", "智者", "莽夫", "腹黑", "傲娇", "病娇", "毒舌", "温柔", "冷酷",
        "阳光", "阴郁", "热血", "冷静", "忠诚", "背叛者", "天选之子", "普通人逆袭",
        "农民", "商人", "书生", "官员", "皇帝", "乞丐", "游侠", "猎人", "渔夫",
        "铁匠", "厨师", "郎中", "说书人", "镖师", "管家", "仆人", "太子", "公主",
        "王爷", "贵妃", "太监", "宫女", "将军", "士兵", "元帅", "军师", "大侠",
        "剑客", "刺客", "杀手", "盗贼", "帮主", "学生", "教师", "医生", "律师",
        "警察", "程序员", "演员", "歌手", "网红", "主播", "作家", "运动员", "穿越者",
        "重生者", "转世者", "异能者", "系统宿主", "天命之子", "私生子", "替身",
        "间谍", "卧底", "精灵", "矮人", "兽人", "龙族", "魔族", "妖族", "神明",
        "天使", "恶魔", "亡灵", "外星人", "族长", "嫡子", "庶子", "兄弟", "姐妹",
        "师徒", "父子", "母子", "夫妻", "恋人", "主仆", "君臣", "盟友", "敌对",
    ]

    if any(kw in tag for kw in element_keywords):
        return "element"
    if any(kw in tag for kw in setting_keywords):
        return "setting"
    if any(kw in tag for kw in style_keywords):
        return "style"
    if any(kw in tag for kw in structure_keywords):
        return "structure"
    if any(kw in tag for kw in chapter_keywords):
        return "chapter_function"
    if any(kw in tag for kw in character_keywords):
        return "character_archetype"

    return "element"


def init_tags():
    """从 tags.yaml 导入标签数据到数据库。"""
    if not TAGS_FILE.exists():
        print(f"警告: 标签文件不存在 {TAGS_FILE}")
        print("跳过标签初始化")
        return

    print(f"读取标签文件: {TAGS_FILE}")
    old_tags = load_yaml(TAGS_FILE)

    print("连接数据库...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    total_tags = 0
    total_synonyms = 0

    # 遍历各维度（跳过固定层和同义词）
    for dimension, dim_data in old_tags.items():
        if dimension in ["channel", "genre", "synonym_map"]:
            continue

        if not isinstance(dim_data, dict):
            continue

        print(f"处理维度: {dimension}")

        for group_name, tags_list in dim_data.items():
            if not isinstance(tags_list, list):
                continue

            for tag in tags_list:
                domain = resolve_domain(dimension, tag)
                is_common = (domain == "common")

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO tags (dimension, tag, domain, group_name, is_common)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (dimension, tag) DO NOTHING
                    """, [dimension, tag, domain, group_name, is_common])

                    if cur.rowcount > 0:
                        total_tags += 1

    # 处理同义词映射
    print("处理同义词映射...")
    synonym_map = old_tags.get("synonym_map", {})

    for standard, synonyms in synonym_map.items():
        if not isinstance(synonyms, list):
            continue

        # 查找标准标签的 dimension 和 domain
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dimension, domain FROM tags WHERE tag = %s AND synonym_of IS NULL
            """, [standard])
            result = cur.fetchone()

        if not result:
            dim = infer_dimension(standard)
            domain = resolve_domain(dim, standard) if dim else "common"

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tags (dimension, tag, domain, is_common)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, [dim, standard, domain, domain == "common"])

            result = (dim, domain)

        dim, dom = result

        for syn in synonyms:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tags (dimension, tag, domain, synonym_of, is_common)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (dimension, tag) DO UPDATE SET synonym_of = %s
                """, [dim, syn, dom, standard, dom == "common", standard])

                if cur.rowcount > 0:
                    total_synonyms += 1

    conn.close()

    print(f"\n标签导入完成!")
    print(f"  新增标签: {total_tags}")
    print(f"  新增同义词: {total_synonyms}")

    # 打印统计
    print_statistics()


def print_statistics():
    """打印各维度统计。"""
    conn = psycopg2.connect(DATABASE_URL)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT dimension, domain, COUNT(*) as count
            FROM tags GROUP BY dimension, domain ORDER BY dimension, domain
        """)

        print("\n各维度标签统计:")
        current_dim = None
        for row in cur.fetchall():
            dim, dom, count = row
            if dim != current_dim:
                print(f"\n{dim}:")
                current_dim = dim
            print(f"  {dom}: {count} 个")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tags WHERE synonym_of IS NOT NULL")
        syn_count = cur.fetchone()[0]
        print(f"\n同义词: {syn_count} 个")

    conn.close()


if __name__ == "__main__":
    init_tags()