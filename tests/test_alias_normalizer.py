from career_graph.normalizer.alias_normalizer import AliasNormalizer


def test_normalize_known_aliases():
    n = AliasNormalizer()
    assert n.normalize("py") == "Python"
    assert n.normalize("PYTHON") == "Python"
    assert n.normalize("amazon web services") == "AWS"


def test_normalize_fallback_titlecase():
    n = AliasNormalizer()
    assert n.normalize("data engineering") == "Data Engineering"
    # dot-containing tokens preserved via alias mapping
    assert n.normalize("node.js") == "Node.js"
