from reviewstats.parse import is_excluded_author


def test_lando_bot_excluded():
    assert is_excluded_author("Lando") is True


def test_normal_author_kept():
    assert is_excluded_author("Paul Adenot") is False
    assert is_excluded_author("alastor0325") is False
