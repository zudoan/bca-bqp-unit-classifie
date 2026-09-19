from preprocessing.normalize import normalize_name, remove_diacritics, to_search_key


def test_normalize_name_collapses_case_whitespace_and_punctuation():
    assert (
        normalize_name("  PHÒNG   Tham mưu - Công an Hà Nội  ")
        == "phòng tham mưu công an hà nội"
    )


def test_remove_vietnamese_diacritics_including_d_stroke():
    assert remove_diacritics("Đơn vị đồn trú") == "Don vi don tru"


def test_search_key_is_accent_insensitive():
    assert to_search_key("Công an Thành phố Hà Nội") == "cong an thanh pho ha noi"


def test_unicode_compatibility_forms_are_normalized():
    assert normalize_name("ＣÔＮＧ  ＡＮ") == "công an"
