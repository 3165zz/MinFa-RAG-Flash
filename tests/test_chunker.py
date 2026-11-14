# -*- coding: utf-8 -*-
"""
test_chunker.py — 切分逻辑的 pytest 用例
=========================================

【思路】
    拿几条"已知正确答案"的条文做断言，守住切分逻辑的关键行为：
    总数 / 条号连续 / id 唯一 / 首条 / 多款边界 / 附则元数据 / 分编 / 中文数字转换。
    这些用例和 validate.py 互补：validate 校验"产物 JSON"，这里校验"切分函数本身"。

【运行】
    pytest            # 在项目根目录运行（pytest.ini 已配置好路径）
"""

import pytest

import chunker
import validate


# ------------------------------------------------------------
# fixture：整个模块只解析一次语料，供所有用例复用（省时）
# ------------------------------------------------------------
@pytest.fixture(scope="module")
def chunks():
    """全部 1260 个 chunk（直接调切分函数，不依赖 JSON 文件）。"""
    return chunker.parse_corpus()


@pytest.fixture(scope="module")
def by_id(chunks):
    """把 chunk 列表转成 {id: chunk} 字典，方便按条号取用。"""
    result = {}
    for c in chunks:
        result[c["id"]] = c
    return result


# ------------------------------------------------------------
# 整体性断言
# ------------------------------------------------------------
def test_total_count(chunks):
    """总数必须恰好 1260——少一条都说明切分漏了。"""
    assert len(chunks) == 1260


def test_article_no_continuous(chunks):
    """条号必须覆盖 1~1260 且不重复（缺失条号检测）。"""
    numbers = set()
    for c in chunks:
        numbers.add(c["article_no"])
    assert numbers == set(range(1, 1261))


def test_id_unique(chunks):
    """id 不能重复。"""
    ids = set()
    for c in chunks:
        assert c["id"] not in ids, f"id 重复：{c['id']}"
        ids.add(c["id"])


def test_required_fields(chunks):
    """每条都必须含全部元数据字段。"""
    fields = ["article_no", "id", "book", "subbook", "chapter", "source_file", "text"]
    for c in chunks:
        for f in fields:
            assert f in c, f"第{c['article_no']}条 缺字段 {f}"


# ------------------------------------------------------------
# 已知条文断言（第 1 / 1165 / 1259 / 1260 条）
# ------------------------------------------------------------
def test_first_article(by_id):
    """第一条：立法目的，编/章/出处/主旨都要对。"""
    c = by_id["第一条"]
    assert c["article_no"] == 1
    assert c["book"] == "第一编　总则"
    assert c["subbook"] == ""
    assert c["chapter"] == "第一章　基本规定"
    assert c["source_file"] == "民法典-第一编-总则.md"
    assert c["text"].startswith("【立法目的】")


def test_article_1165_paragraph_boundary(by_id):
    """第 1165 条有两款，必须用换行保留款边界，不能揉成一段。"""
    c = by_id["第一千一百六十五条"]
    assert c["book"] == "第七编　侵权责任"
    assert "\n" in c["text"], "多款条文的款边界丢失"
    paragraphs = c["text"].split("\n")
    assert len(paragraphs) == 2
    assert paragraphs[0].startswith("【过错责任原则】")


def test_article_1259_fuzhe_metadata(by_id):
    """第 1259 条属附则：编名仍是第七编，章名必须为空（不能停留在第十章）。"""
    c = by_id["第一千二百五十九条"]
    assert c["article_no"] == 1259
    assert c["book"] == "第七编　侵权责任"
    assert c["subbook"] == ""
    assert c["chapter"] == ""


def test_article_1260_last(by_id):
    """第 1260 条是末条：施行日期及旧法废止。"""
    c = by_id["第一千二百六十条"]
    assert c["article_no"] == 1260
    assert c["chapter"] == ""
    assert "2021年1月1日" in c["text"]
    assert c["text"].startswith("【施行日期及旧法废止】")


# ------------------------------------------------------------
# 分编元数据（合同编有三个分编）
# ------------------------------------------------------------
def test_subbook(by_id):
    """第 463 条在合同编第一分编；分编信息不能丢、也不能当成章。"""
    c = by_id["第四百六十三条"]
    assert c["book"] == "第三编　合同"
    assert c["subbook"] == "第一分编　通则"
    assert c["chapter"] == "第一章　一般规定"


# ------------------------------------------------------------
# 中文数字转整数（article_no 的基础）
# ------------------------------------------------------------
def test_cn_to_int():
    """覆盖个位/十位/百位/千位/含零等关键情形。"""
    cases = [
        ("一", 1),
        ("十", 10),
        ("二十", 20),
        ("一百零一", 101),
        ("二百六十六", 266),
        ("一千一百六十五", 1165),
        ("一千二百六十", 1260),
    ]
    for text, expected in cases:
        assert chunker.cn_to_int(text) == expected, f"{text} 转换错误"


# ------------------------------------------------------------
# 健壮性：frontmatter 仅在文件头识别
# ------------------------------------------------------------
def test_frontmatter_guard(tmp_path):
    """没有 frontmatter 的文件，正文里的 --- 分隔线不能吞掉后面的条文。

    旧写法会把正文第一条 --- 误判为 frontmatter 开头，把后续内容全部吞掉；
    修复后只有"文件第一行就是 ---"才认定 frontmatter。
    """
    content = "# 测试编\n\n---\n\n- 第一条\u3000【测试】这是正文。\n"
    fp = tmp_path / "测试.md"
    fp.write_text(content, encoding="utf-8")
    result = chunker.parse_file(fp)
    assert len(result) == 1
    assert result[0]["id"] == "第一条"
    assert "这是正文" in result[0]["text"]


# ------------------------------------------------------------
# 反向验证：校验器必须能抓出问题（证明它不是摆设）
# ------------------------------------------------------------
def test_validate_catches_problems():
    """故意制造缺条、括号错配，validate 必须报错。"""
    good = chunker.parse_corpus()
    bad = []
    for c in good:
        bad.append(dict(c))  # 浅拷贝，避免污染原数据
    bad.pop(0)  # 删掉第一条 → 总数不足 + 缺失条号 1
    bad[0]["text"] = bad[0]["text"].replace("【", "【【", 1)  # 破坏括号配对
    errors = validate.validate(bad)
    joined = " ".join(errors)
    assert len(errors) > 0
    assert "缺失" in joined
    assert "括号" in joined