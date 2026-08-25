"""
Tests du handler CSV (core/csv_handler.py) -- premiere verification reelle
depuis sa creation (son propre commentaire de tete de module notait
explicitement l'absence de validation contre un vrai fichier Empyrion).

Un vrai bug trouve et corrige lors de cette premiere verification : la
detection automatique du dialecte (csv.Sniffer) peut se tromper sur
doublequote (le detecte a tort a False sur un vrai PDA.csv contenant des
guillemets imbriques), causant un doublement des guillemets a chaque
sauvegarde -- meme categorie de defaillance de detection deja connue et deja
contournee pour has_header().
"""
from pathlib import Path

from core.csv_handler import parse_csv_text, render_csv

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pda_scenario" / "PDA.csv"


def test_round_trip_perfect_on_fixture_with_embedded_quotes():
    original = FIXTURE_PATH.read_bytes()
    doc = parse_csv_text(original.decode("utf-8"))
    rendered = render_csv(doc).encode("utf-8")
    assert rendered == original


def test_embedded_quotes_correctly_unescaped_on_parse():
    """Regression cle : 'Is it too late to say ""We come in peace""?' doit
    devenir 'Is it too late to say "We come in peace"?' apres analyse, pas
    conserver les guillemets doubles bruts."""
    doc = parse_csv_text(FIXTURE_PATH.read_text(encoding="utf-8"))
    value = doc.rows[0][1]
    assert value == 'Is it too late to say "We come in peace"?'
    assert '""' not in value


def test_doublequote_forced_true_even_when_sniffer_detects_false():
    """Regression directe : confirme que le dialecte retourne toujours
    doublequote=True, meme dans les cas ou le Sniffer se trompe (le
    fichier reel PDA.csv de 9267 lignes en est un exemple confirme)."""
    from core.csv_handler import _detect_dialect
    dialect = _detect_dialect(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert dialect.doublequote is True


def test_render_does_not_double_escape_already_correct_value():
    """Un aller-retour repete (parse -> render -> parse -> render) ne doit
    jamais accumuler de guillemets supplementaires."""
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    doc1 = parse_csv_text(text)
    rendered1 = render_csv(doc1)
    doc2 = parse_csv_text(rendered1)
    rendered2 = render_csv(doc2)
    assert rendered1 == rendered2
    assert doc1.rows == doc2.rows
