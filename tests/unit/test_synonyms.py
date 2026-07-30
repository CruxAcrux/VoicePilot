"""Unit tests for synonym normalisation."""

from voicepilot.parser.synonyms import normalise_text


def test_verb_synonym_open():
    assert "open" in normalise_text("launch firefox")
    assert "open" in normalise_text("start firefox")


def test_verb_synonym_close():
    assert "close" in normalise_text("quit firefox")
    assert "close" in normalise_text("exit terminal")


def test_verb_synonym_create():
    assert "create" in normalise_text("make folder projects")


def test_app_synonym_terminal():
    result = normalise_text("open console")
    assert "terminal" in result


def test_folder_synonym_downloads():
    result = normalise_text("open download folder")
    assert "downloads" in result


def test_case_insensitive():
    result = normalise_text("LAUNCH FIREFOX")
    assert "open" in result.lower()
    assert "firefox" in result.lower()


def test_no_mutation_of_canonical():
    """Canonical words should not be double-replaced."""
    result = normalise_text("open firefox")
    assert result.count("open") == 1
