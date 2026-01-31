from app.pipeline.sentence_chunker import SentenceChunker


def test_single_sentence():
    c = SentenceChunker()
    assert c.add_token("Bonjour") == []
    assert c.add_token(" les") == []
    # Period at end-of-buffer triggers sentence detection immediately
    assert c.add_token(" enfants.") == ["Bonjour les enfants."]


def test_multiple_sentences():
    c = SentenceChunker()
    sentences = c.add_token("Salut! Comment ça va? ")
    assert sentences == ["Salut!", "Comment ça va?"]


def test_flush_remaining():
    c = SentenceChunker()
    c.add_token("Pas de point final")
    assert c.flush() == "Pas de point final"


def test_flush_empty():
    c = SentenceChunker()
    assert c.flush() is None


def test_exclamation_and_question():
    c = SentenceChunker()
    result = c.add_token("Super! Tu veux jouer? ")
    assert result == ["Super!", "Tu veux jouer?"]


def test_ellipsis():
    c = SentenceChunker()
    result = c.add_token("Hmm… ")
    assert result == ["Hmm…"]


def test_reset():
    c = SentenceChunker()
    c.add_token("Hello")
    c.reset()
    assert c.flush() is None
