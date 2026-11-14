# -*- coding: utf-8 -*-
"""
validate.py — MinFa-RAG-Flash 语料切分结果的自动化校验
=======================================================

【为什么需要它】
    "1260 条没错"不能靠手工数，要让系统每次都能自动保证。
    本脚本对 data/chunks.json 做一组硬性断言，任何一条不满足就报错退出。
    以后换语料源、改切分逻辑，跑一遍就能立刻发现"缺条 / 重复 / 括号错配"等问题。

【校验项】
    1. 总数恰好 1260
    2. 条号 1~1260 连续，无缺失、无重复（缺失条号检测）
    3. id 唯一
    4. 每条字段齐全（article_no/id/book/subbook/chapter/source_file/text）
    5. text 非空，且以句末标点（。？！；）结尾
    6. 【主旨】括号配对（【 与 】 数量相等）
    7. book 非空；source_file 是真实存在的语料文件
    8. id 与 article_no 互相吻合（中文条号转整数后一致）
    9. 附则两条（1259/1260）归入第七编、章名为空

【用法】
    python validate.py        # 全部通过退出码 0；有失败退出码 1（可用于 CI）
"""

import json
import sys
from pathlib import Path

import chunker  # 复用 cn_to_int / list_corpus_files，保证校验与切分用同一套逻辑

PROJECT_ROOT = Path(__file__).resolve().parent
CHUNKS_FILE = PROJECT_ROOT / "data" / "chunks.json"

EXPECTED_TOTAL = 1260          # 民法典总条数
SENTENCE_END = "。？！；"        # 允许的句末标点
REQUIRED_FIELDS = ["article_no", "id", "book", "subbook",
                   "chapter", "source_file", "text"]


def load_chunks():
    """读取切分产物 chunks.json；不存在则提示先跑 chunker.py。"""
    if not CHUNKS_FILE.exists():
        print("[错误] 找不到 data/chunks.json，请先运行：python chunker.py")
        sys.exit(1)
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def validate(chunks):
    """
    对 chunk 列表逐项校验，返回错误信息列表（空列表 = 全部通过）。
    把"校验逻辑"和"打印/退出"分开，方便测试直接调用本函数。
    """
    errors = []

    # ---------- 1. 总数 ----------
    if len(chunks) != EXPECTED_TOTAL:
        errors.append(f"总数应为 {EXPECTED_TOTAL}，实际 {len(chunks)}")

    # ---------- 2. 条号连续 + 缺失/重复检测 ----------
    number_set = set()      # 出现过的条号
    duplicate_set = set()   # 重复出现的条号
    for c in chunks:
        no = c["article_no"]
        if no in number_set:
            duplicate_set.add(no)
        number_set.add(no)

    missing = []
    for n in range(1, EXPECTED_TOTAL + 1):
        if n not in number_set:
            missing.append(n)
    if missing:
        errors.append(f"缺失条号（共 {len(missing)} 个）：{missing}")
    if duplicate_set:
        errors.append(f"重复条号：{sorted(duplicate_set)}")

    # ---------- 3. id 唯一 ----------
    id_set = set()
    id_dup = set()
    for c in chunks:
        cid = c["id"]
        if cid in id_set:
            id_dup.add(cid)
        id_set.add(cid)
    if id_dup:
        errors.append(f"重复 id：{sorted(id_dup)}")

    # ---------- 7（部分）. source_file 必须是真实语料文件 ----------
    valid_files = set()
    for fp in chunker.list_corpus_files():
        valid_files.add(fp.name)

    # ---------- 4~9. 逐条检查 ----------
    for c in chunks:
        no = c["article_no"]
        tag = f"第{no}条"  # 报错时用来定位是哪一条

        # 4. 字段齐全
        for field in REQUIRED_FIELDS:
            if field not in c:
                errors.append(f"{tag} 缺字段 {field}")

        text = c.get("text", "")
        # 5. text 非空 + 句末标点
        if text == "":
            errors.append(f"{tag} text 为空")
        elif text[-1] not in SENTENCE_END:
            errors.append(f"{tag} text 未以句末标点结尾：…{text[-12:]}")

        # 6. 【主旨】括号配对
        if text.count("【") != text.count("】"):
            errors.append(f"{tag} 【】括号不配对（【{text.count('【')} 个 / 】{text.count('】')} 个）")

        # 7. book 非空、source_file 合法
        if c.get("book", "") == "":
            errors.append(f"{tag} book 为空")
        if c.get("source_file", "") not in valid_files:
            errors.append(f"{tag} source_file 不是已知语料文件：{c.get('source_file')}")

        # 8. id 与 article_no 吻合（把中文条号转整数比对）
        cid = c.get("id", "")
        if cid.startswith("第") and cid.endswith("条"):
            id_core = cid[1:-1]  # 去掉"第"和"条"，剩中文数字
            if chunker.cn_to_int(id_core) != no:
                errors.append(f"{tag} id({cid}) 与 article_no({no}) 不一致")
        else:
            errors.append(f"{tag} id 格式异常：{cid}")

        # 9. 附则两条归入第七编、章名为空
        if no == 1259 or no == 1260:
            if not c.get("book", "").startswith("第七编"):
                errors.append(f"{tag} 附则条文 book 应为第七编，实际 {c.get('book')}")
            if c.get("chapter", "") != "":
                errors.append(f"{tag} 附则条文 chapter 应为空，实际 {c.get('chapter')}")

    return errors


def main():
    chunks = load_chunks()
    errors = validate(chunks)

    print("=" * 60)
    print("MinFa-RAG-Flash · 语料切分校验")
    print("=" * 60)
    print(f"  待校验块数：{len(chunks)}")
    print()

    if len(errors) == 0:
        print("  [OK] 全部校验通过：总数 / 条号连续 / id 唯一 / 字段齐全 /")
        print("       句末标点 / 括号配对 / 出处合法 / 附则元数据 均正常。")
        sys.exit(0)
    else:
        print(f"  [FAIL] 发现 {len(errors)} 处问题：")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()