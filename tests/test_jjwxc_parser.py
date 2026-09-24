from metafinder.sources.generic import GenericPageParser


def test_jjwxc_patch_cleans_wrapped_title_author_and_cover():
    html = """
    <html>
      <head><title>《卖脸花瓶是机甲大神》逢行_晋江文学城_【原创小说|言情小说】</title></head>
      <body>
        <img src="https://pic1.imgdb.cn/item/6808e4df58cb8da5c8c6a495.jpg" />
      </body>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://www.jjwxc.net/onebook.php?novelid=7370132", html)

    assert candidate.source_name == "晉江文學城"
    assert candidate.metadata.title == "賣臉花瓶是機甲大神"
    assert candidate.metadata.authors == ["逢行"]
    assert candidate.metadata.publisher == "網版"
    assert candidate.metadata.cover_url == "https://pic1.imgdb.cn/item/6808e4df58cb8da5c8c6a495.jpg"
    assert "jjwxc-page" in candidate.evidence


def test_jjwxc_patch_extracts_description_and_tags():
    html = """
    <html>
      <head><title>《制霸手术室》时逢而已_晋江文学城_【原创小说|言情小说】</title></head>
      <body>
        文案
        林熙冬上辈子在急诊科，兢兢业业，最后累死在手术台上。
        重生归来，她再次踏上医学之路。
        内容标签：
        重生
        现代架空
        轻松
        林熙冬
        劝人学医遭雷劈
        搜索关键字：主角：林熙冬
        配角：很多医生
        其它：医学系统
        一句话简介：人生建议：对医生好点
        文章基本信息
        文章类型：
        原创-言情-近代现代-剧情
      </body>
    </html>
    """

    candidate = GenericPageParser().parse_html("https://www.jjwxc.net/onebook.php?novelid=5149951", html)

    assert "林熙冬上輩子在急診科" in candidate.metadata.description
    assert "重生" in candidate.metadata.tags
    assert "現代架空" in candidate.metadata.tags
    assert "言情" in candidate.metadata.tags
    assert "林熙冬" not in candidate.metadata.tags
    assert "勸人學醫遭雷劈" not in candidate.metadata.tags
    assert "很多醫生" not in candidate.metadata.tags
def test_description_stops_at_next_book_promotion_but_skips_leading_notice():
    from metafinder.sources.generic import _jjwxc_description

    text = "文案\n《別本》預收，點進專欄收藏\n少女穿越成反派家的女兒。\n下一本預收《古樹》\n這是另一位主角的故事。\n內容標籤："
    assert _jjwxc_description(text) == "少女穿越成反派家的女兒。"
