from chaz_songbook import lyrics as lx


def test_syllables_dictionary_words():
    assert lx.word_syllables("money") == 2
    assert lx.word_syllables("beautiful") == 3
    assert lx.word_syllables("gold") == 1
    assert lx.word_syllables("comin'") == 2
    assert lx.line_syllables("Gold on my teeth when the sun hit the glass") == 10


def test_syllables_unknown_word_heuristic():
    assert lx.word_syllables("skrrtadoodle") >= 3
    assert lx.heuristic_syllables("") == 0


def test_stats_and_bars():
    text = "[Hook - ad-libs]\nline one here\n\nline two here\n"
    st = lx.stats(text)
    assert st["bars"] == 2
    assert st["words"] == 9  # bracketed words still count as words
    assert lx.count_bars("") == 0


def test_last_word():
    assert lx.last_word("I'm countin' up the cash, yeah!") == "yeah"
    assert lx.last_word("   ") == ""


def test_rhymes_perfect_and_near():
    r = lx.rhymes("glass")
    assert {"class", "pass", "grass"} <= set(r["perfect"])
    assert "glass" not in r["perfect"]
    near = lx.rhymes("bag")["near"]
    assert near and all(w != "bag" for w in near)


def test_rhymes_multisyllable():
    r = lx.rhymes("money")
    assert "honey" in r["perfect"] or "funny" in r["perfect"]


def test_rhyme_unknown_word_falls_back_to_spelling():
    r = lx.rhymes("blorpgrass")
    assert r["perfect"]  # spelling tail match


def test_empty_rhyme():
    assert lx.rhymes("") == {"perfect": [], "near": []}
