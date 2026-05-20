from reviewstats.aliases import canonicalize_author


def test_known_alias_maps():
    assert canonicalize_author("alastor0325") == "Alastor Wu"
    assert canonicalize_author("alwu") == "Alastor Wu"
    assert canonicalize_author("az") == "azebrowski"


def test_unknown_name_passes_through():
    assert canonicalize_author("Paul Adenot") == "Paul Adenot"
    assert canonicalize_author("Some Random Author") == "Some Random Author"


def test_canonical_name_passes_through():
    assert canonicalize_author("Alastor Wu") == "Alastor Wu"
