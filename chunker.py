"""
chunker.py — MinFa-RAG-Flash 阶段 1：语料切分脚本
===================================================

【在整个 RAG 流程里的位置】

    语料切分(本脚本) → 向量化(embedding) → 检索(retrieval) → 生成(generation)
         ↑ 你在这里

本脚本是 RAG 管线的第一步：把原始法条文本拆成一个个可检索的最小单元（chunk）。
切分质量直接决定后续检索的精度——块太大则噪声多，块太小则语义不完整。
我们选择"一条法条 = 一个 chunk"，因为法条本身就是法律文本中最自然、最完整的语义单元。

【输入】
    corpus/ 目录下的 7 个 Markdown 文件，每个文件对应民法典的一编。
    文件格式：YAML frontmatter + # 书名 + ## 编标题 + ### 章标题 + 条文列表项。

【输出】
    data/chunks.json —— 一个 JSON 文件，结构为：
    {
      "chunks": [
        {"id": "第一条", "book": "第一编　总则", "subbook": "", "chapter": "第一章　基本规定", "text": "【立法目的】..."},
        ...
      ]
    }

【四条切分规则及其由来】

规则 1：只有行首匹配 "- 第<中文数字>条　" 才算新条文开始。
    → 防的坑：条文正文里有大量交叉引用（如"依据本法第一百四十二条第一款"），
      如果不锚定行首 + "- " 前缀，裸正则 findall 会把这些引用也当成新条文。
      之前实测第三编会多出 7 条假阳性（533 vs 真实的 526）。

规则 2：非空、又不匹配任何规则的裸行 → 是上一条的续行（即该条的下一“款”），
    用换行符 "\n" 拼接到当前块 text 末尾。
    → 防的坑：多段条文（如第 1165 条有两款）的第二款起在源文件里没有 "- " 前缀，
      是"裸行"。如果不合并，这些内容就会丢失或变成无主碎片。
    → 为什么用 "\n" 而不是直接相连：法律引用讲究"第X条第Y款"，款与款的边界
      必须保留。直接相接会把多款揉成一段，丢掉款边界，影响 LLM 引用和人工核对。

规则 3：frontmatter 和所有 # 开头的标题行跳过，但提取编/分编/章作为元数据。
    → 编名(book)：直接取 frontmatter 里的 book 字段，整编恒定。这样文末的
      "## 附则" 不会被误当成编名（否则最后两条的出处会变成"附则·第十章…"）。
    → 分编(subbook)：合同编/物权编有"第X分编"，它和"章"都用 ### 标记，
      靠是否含"分编"二字区分，单独存入 subbook，遇到新分编把章重置。
    → 章名(chapter)：### 里不含"分编"的即章名；遇到附则/新分编时重置为空。
    → 防的坑：标题行不是法条内容，混入 chunk 会污染检索结果。

规则 4：【主旨标题】保留在 text 里，不删。
    → 防的坑：主旨标题是条文的"摘要"，包含关键法律术语（如"过错责任原则"），
      对 embedding 语义匹配有正面作用。v1 先保留，留到 v4 评测再做去留对比实验。
"""

import json
import os
import re
from pathlib import Path


# ============================================================
# 路径配置
# ============================================================
# 用 Path(__file__).resolve().parent 定位项目根目录，而不是依赖 os.getcwd()。
# 为什么：这个项目之前踩过坑——脚本放在子目录里运行时，相对路径会指向错误位置。
# __file__ 是脚本自身的绝对路径，.parent 取其所在目录，无论从哪里调用都能正确定位。

PROJECT_ROOT = Path(__file__).resolve().parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "chunks.json"


# ============================================================
# 正则表达式
# ============================================================
# 规则 1 的核心：匹配条文起始行。
#
# 拆解这个正则：
#   ^           —— 锚定行首（防止匹配到正文中间的"本法第X条"交叉引用）
#   -           —— 字面量减号（Markdown 列表项的前缀）
#   (空格)      —— 列表标记 "- " 后面的空格
#   第          —— 字面量"第"
#   ([一二三四五六七八九十百千零]+)  —— 捕获组：一个或多个中文数字字符
#   条          —— 字面量"条"
#   \u3000      —— 全角空格（Unicode U+3000），条号和正文之间的分隔符
#
# 注意事项：
#   - 字符集 [一二三四五六七八九十百千零] 后面的 + 作用于整个字符集（方括号闭合了），
#     而不是只作用于最后一个字符。之前踩过没闭合的坑（见 common_pitfalls 记录）。
#   - 这里用 \u3000 而不是直接写全角空格字符，是为了代码可读性（明确告诉读者这是全角空格）。

ARTICLE_PATTERN = re.compile(r"^- 第([一二三四五六七八九十百千零]+)条\u3000")


# ============================================================
# 文件处理顺序
# ============================================================
# 按照民法典的编排顺序处理，这样输出的 chunks.json 里条文是有序的。

FILE_ORDER = [
    "民法典-第一编-总则.md",
    "民法典-第二编-物权.md",
    "民法典-第三编-合同.md",
    "民法典-第四编-人格权.md",
    "民法典-第五编-婚姻家庭.md",
    "民法典-第六编-继承.md",
    "民法典-第七编-侵权责任.md",
]


# ============================================================
# 核心函数：解析单个文件
# ============================================================

def parse_file(filepath):
    """
    解析一个 Markdown 语料文件，返回该文件中所有条文的 chunk 列表。

    参数：
        filepath: Path 对象，指向 corpus/ 下的某个 .md 文件

    返回：
        list of dict，每个 dict 形如：
        {"id": "第一条", "book": "第一编　总则", "subbook": "", "chapter": "第一章　基本规定", "text": "【立法目的】..."}
    """

    # ---------- 第一步：读取文件全部内容 ----------
    # encoding="utf-8" 必须显式指定，因为 Windows 默认编码是 GBK/CP936，
    # 不指定会报 UnicodeDecodeError。
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 按换行符拆成行列表。splitlines() 会自动处理 \n 和 \r\n，
    # 并且不会在最后一行多加一个空字符串（比 split("\n") 更安全）。
    lines = content.splitlines()

    # ---------- 第二步：初始化状态变量 ----------
    chunks = []           # 存放本文件解析出的所有 chunk
    file_book = ""        # 本文件的编名，从 frontmatter 的 book 字段读取（整编恒定）
    current_book = ""     # 当前所属"编"（frontmatter 处理完后设为 file_book）
    current_subbook = ""  # 当前所属"分编"（合同编/物权编才有，从含"分编"的 ### 标题提取）
    current_chapter = ""  # 当前所属"章"（从不含"分编"的 ### 标题提取）
    current_chunk = None  # 当前正在构建的 chunk（遇到续行时往里追加文本）

    # frontmatter 状态机：文件开头两个 "---" 之间的内容要跳过
    in_frontmatter = False
    frontmatter_done = False  # 标记 frontmatter 是否已经处理完毕

    # ---------- 第三步：逐行扫描 ----------
    for line in lines:

        # ===== 处理 frontmatter（规则 3 的一部分）=====
        # frontmatter 是文件最开头被两个 "---" 包围的 YAML 元数据块。
        # 它包含 title/passed/book 三个字段，是给文档管理用的，不是法条内容。
        if not frontmatter_done:
            if line.strip() == "---":
                if not in_frontmatter:
                    # 遇到第一个 "---"，进入 frontmatter 区域
                    in_frontmatter = True
                    continue
                else:
                    # 遇到第二个 "---"，frontmatter 结束
                    in_frontmatter = False
                    frontmatter_done = True
                    # 编名以 frontmatter 的 book 字段为准，整编恒定，
                    # 后面不再被任何 ## 标题（尤其是"## 附则"）覆盖。
                    current_book = file_book
                    continue
            if in_frontmatter:
                # 在 frontmatter 内部：只挑出 book 字段记下，其余行跳过
                if line.startswith("book:"):
                    file_book = line[len("book:"):].strip()
                continue

        # ===== 处理标题行（规则 3）=====
        # 所有以 "#" 开头的行都是 Markdown 标题，不是法条内容，需要跳过。
        # 但我们要从中提取分编名和章名作为元数据（编名已用 frontmatter 的 book）。
        if line.startswith("#"):
            if line.startswith("## ") and not line.startswith("### "):
                # "## " 级别有两种："## 第X编 …"（主编标题）和文末的 "## 附则"。
                # 注意：必须先判断 "## " 且不是 "### "，因为 "###" 也以 "##" 开头。
                # 编名不从这里取（已用 frontmatter 的 book，恒定不变），
                # 否则 "## 附则" 会把最后两条的编名误改成"附则"。
                # 无论主编还是附则，都代表进入新的顶层区块，分编/章一律重置。
                current_subbook = ""
                current_chapter = ""
            elif line.startswith("### ") and not line.startswith("#### "):
                # "### " 级别混着两种："第X分编 …"（分编）和 "第X章 …"（章）。
                title = line[4:].strip()  # 去掉 "### " 四个字符
                if "分编" in title:
                    # 分编是"编"之下、"章"之上的一层（仅合同编/物权编有）。
                    # 单独存进 subbook，不能当成章；进入新分编时把章重置。
                    current_subbook = title
                    current_chapter = ""
                else:
                    # 不含"分编"的就是章名，如 "第一章　基本规定"
                    current_chapter = title
            # "# 书名" 和 "#### 节名" 直接跳过，不记录
            # （节是章下面的细分，v1 不需要这层元数据）
            continue

        # ===== 处理条文起始行（规则 1）=====
        # 用正则检查这一行是不是以 "- 第X条　" 开头。
        match = ARTICLE_PATTERN.match(line)
        if match:
            # 匹配成功 → 这是一条新法条的起始行

            # 先把上一条 chunk 存入列表（如果有的话）
            if current_chunk is not None:
                chunks.append(current_chunk)

            # 从正则捕获组提取中文数字部分，拼成完整条号
            # 例如 match.group(1) = "一千一百六十五" → id = "第一千一百六十五条"
            article_number = match.group(1)
            article_id = "第" + article_number + "条"

            # 提取条文正文：去掉 "- 第X条　" 前缀后的剩余部分
            # match.end() 返回正则匹配结束的字符位置，从那之后就是正文（含【主旨标题】）
            article_text = line[match.end():]

            # 创建新的 chunk 字典
            # 元数据按层级排列：编(book) > 分编(subbook) > 章(chapter)。
            # 没有分编的编（如总则编），subbook 为空字符串。
            current_chunk = {
                "id": article_id,
                "book": current_book,
                "subbook": current_subbook,
                "chapter": current_chapter,
                "text": article_text,
            }
            continue

        # ===== 处理续行（规则 2）=====
        # 走到这里说明：这一行不是 frontmatter、不是标题、也不是新条文起始。
        # 如果它不是空行，那就是上一条法条的续行，也就是该条的下一"款"。
        if line.strip() != "":
            # 有实际内容的裸行 → 用换行符 "\n" 拼接到当前 chunk 的 text 末尾。
            # 为什么用 "\n" 而不是直接相连：源文件里每一款各占一行，款与款之间
            # 本就有分段边界。法律引用讲究"第X条第Y款"，必须把这个边界保留下来，
            # 否则多款会被揉成一段，LLM 引用和人工核对都没法定位到具体的款。
            if current_chunk is not None:
                current_chunk["text"] = current_chunk["text"] + "\n" + line.strip()
            # 如果 current_chunk 是 None（理论上不会发生，除非文件格式异常），
            # 则忽略这行。这是一种防御性编程。

        # 空行（line.strip() == ""）→ 什么都不做，直接跳过。
        # 空行在 Markdown 里是段落分隔符，不携带任何法条内容。

    # ---------- 第四步：别忘了最后一条 ----------
    # 循环结束后，最后一条 chunk 还暂存在 current_chunk 里，需要追加进列表。
    # 这是一个经典的"边界条件"——新手容易忘记处理循环外的最后一条数据。
    if current_chunk is not None:
        chunks.append(current_chunk)

    return chunks


# ============================================================
# 主函数：遍历文件、汇总结果、写入 JSON
# ============================================================

def main():
    """
    主流程：
    1. 检查 corpus/ 目录是否存在
    2. 按顺序解析 7 个 md 文件
    3. 打印每个文件的块数（方便肉眼核对）
    4. 把所有块汇总，写入 data/chunks.json
    5. 打印首尾块的预览信息（快速验证切分是否正确）
    """

    print("=" * 60)
    print("MinFa-RAG-Flash · 阶段 1 · 语料切分")
    print("=" * 60)
    print()

    # --- 检查语料目录是否存在 ---
    if not CORPUS_DIR.exists():
        print(f"[错误] 语料目录不存在：{CORPUS_DIR}")
        print("请确认 corpus/ 目录在项目根目录下，且包含 7 个 .md 文件。")
        return

    # --- 逐个文件解析 ---
    all_chunks = []  # 汇总所有文件的 chunk

    for filename in FILE_ORDER:
        filepath = CORPUS_DIR / filename

        # 检查文件是否存在
        if not filepath.exists():
            print(f"[警告] 文件不存在，跳过：{filename}")
            continue

        # 调用 parse_file 解析这个文件
        file_chunks = parse_file(filepath)

        # 打印这个文件的块数
        print(f"  {filename}  →  {len(file_chunks)} 条")

        # 把本文件的块追加到总列表
        all_chunks = all_chunks + file_chunks

    # --- 打印汇总信息 ---
    print()
    print(f"  总块数：{len(all_chunks)}")
    print()

    # --- 首尾块预览（方便用户肉眼自检）---
    if len(all_chunks) > 0:
        first = all_chunks[0]
        last = all_chunks[-1]
        print("  ── 首块预览 ──")
        print(f"  id   : {first['id']}")
        print(f"  text : {first['text'][:40]}...")
        print()
        print("  ── 末块预览 ──")
        print(f"  id   : {last['id']}")
        print(f"  text : {last['text'][:40]}...")
        print()

    # --- 写入 JSON 文件 ---
    # 如果 data/ 目录不存在就创建它（exist_ok=True 表示已存在也不报错）
    os.makedirs(DATA_DIR, exist_ok=True)

    # 构建输出数据结构
    output_data = {
        "chunks": all_chunks
    }

    # 写入文件
    # ensure_ascii=False：让中文直接写入，不要转义成 \uXXXX（否则人类没法读）
    # indent=2：缩进 2 空格，让 JSON 文件有格式、可读
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 已写入：{OUTPUT_FILE}")
    print()


# ============================================================
# 入口：只有直接运行这个脚本时才执行 main()
# ============================================================
# 如果别的脚本 import chunker，不会自动执行切分（这是 Python 的标准写法）。

if __name__ == "__main__":
    main()
