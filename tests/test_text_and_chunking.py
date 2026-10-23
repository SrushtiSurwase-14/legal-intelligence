from app.ingestion import chunk_text
from app.textutil import pick_sentences, query_terms, quantities, stem, topics_of


def test_stemmer_groups_related_words():
    assert stem("registration") == stem("registered") == stem("register") == "regist"
    assert stem("hours") == stem("hour")
    assert stem("employees") == stem("employer") == "employ"


def test_query_terms_drop_stopwords_and_numbers():
    assert query_terms("What is the maximum number of hours in 2020?") == ["hour"]


def test_quantities_extracts_units():
    q = quantities("employing 10 or more persons within 30 days; fine of 5000 units; 9 hours")
    assert q == {"persons": {10}, "days": {30}, "units": {5000}, "hours": {9}}


def test_topics():
    assert "registration" in topics_of("must be registered")
    assert "penalty" in topics_of("punishable with a fine")


def test_chunks_follow_sections_and_offsets_are_exact():
    text = "Preamble line.\n\nSection 1. Alpha. First text here.\n\nSection 2. Beta. Second text here.\n"
    chunks = chunk_text("d", text)
    assert [c.section for c in chunks] == ["Preamble", "Section 1", "Section 2"]
    for c in chunks:
        assert text[c.start:c.end] == c.text           # offsets let evidence be re-verified
    assert chunks[1].section_id == "1"


def test_paragraph_fallback_when_no_sections():
    chunks = chunk_text("b", "First paragraph here.\n\nSecond paragraph here.")
    assert [c.section for c in chunks] == ["Paragraph 1", "Paragraph 2"]


def test_long_sections_are_split_but_keep_section_label():
    text = "Section 1. " + " ".join(f"Sentence number {i} is here." for i in range(80))
    chunks = chunk_text("d", text, max_chars=300)
    assert len(chunks) > 1 and {c.section for c in chunks} == {"Section 1"}
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_pick_sentences_returns_verbatim_span():
    t = "Section 4. Daily hours. No employee shall work more than 9 hours in a day. Other text."
    s, e = pick_sentences(t, query_terms("how many hours per day"))
    assert "9 hours" in t[s:e] and t[s:e] in t
