"""Unit tests for synonym normalisation."""

from voicepilot.parser.synonyms import normalise_text


def test_verb_synonym_open():
    assert "öppna" in normalise_text("öppnar firefox")
    assert "öppna" in normalise_text("aktivera firefox")


def test_verb_synonym_close():
    assert "stäng" in normalise_text("stänger firefox")
    assert "stäng" in normalise_text("stängde firefox")


def test_verb_synonym_create():
    assert "skapa" in normalise_text("bygg mapp projects")


def test_app_synonym_terminal():
    result = normalise_text("öppna konsolen")
    assert "terminal" in result


def test_folder_synonym_downloads():
    result = normalise_text("öppna hämtade filer")
    assert "nedladdningar" in result


def test_case_insensitive():
    result = normalise_text("ÖPPNAR FIREFOX")
    assert "öppna" in result.lower()
    assert "firefox" in result.lower()


def test_no_mutation_of_canonical():
    """Canonical words should not be double-replaced."""
    result = normalise_text("öppna firefox")
    assert result.count("öppna") == 1
