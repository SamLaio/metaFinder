from metafinder.tags import author_region_tags


def test_verified_guo_nationality_does_not_guess_other_chinese_names():
    assert author_region_tags(['郭恆鈺']) == ['德國']
    assert author_region_tags(['郭恆玉','郭先生','王小明']) == []


def test_verified_junzi_region_requires_exact_name():
    assert author_region_tags(['君子以澤']) == ['中國']
    assert author_region_tags(['君子以澤同名者','春刀寒','矜以','陳十三']) == []
