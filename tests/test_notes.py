"""search_notes ve sentetik operasyonel notlar birim testleri (ROADMAP Faz 6)."""
from unittest.mock import MagicMock

from kervansaray.query_pipeline import format_narrative
from kervansaray.synth.notes import OPERATIONAL_NOTES, get_synthetic_notes
from kervansaray.tools.dispatcher import dispatch_tool
from kervansaray.tools.notes import search_notes
from kervansaray.tools.types import ToolResult


def test_synthetic_notes_structure():
    notes = get_synthetic_notes()
    assert len(notes) == 15
    assert len(OPERATIONAL_NOTES) == 15

    for n in notes:
        assert "ts" in n
        assert "author" in n
        assert "body" in n
        assert len(str(n["body"])) > 10


def test_search_notes_sql_building():
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "id": 1,
            "ts": "2026-04-02T08:30:00+03:00",
            "author": "Yönetim",
            "body": "VIP misafir prosedürü",
        },
    ]
    mock_db.execute.return_value = mock_result

    res = search_notes(mock_db, query="VIP", author="Yönetim", limit=5)
    assert res.tool == "search_notes"
    assert res.scalar == 1
    assert len(res.rows) == 1
    assert res.rows[0]["author"] == "Yönetim"

    # SQL ve parametre kontrolü
    call_args = mock_db.execute.call_args
    assert call_args is not None
    sql_text, params = call_args[0]
    assert "%VIP%" in params["term"]
    assert "%Yönetim%" in params["author"]
    assert params["limit"] == 5


def test_search_notes_wildcard_escaping():
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    search_notes(mock_db, query="100%_guvenlik\\test", author="admin_%")
    call_args = mock_db.execute.call_args
    assert call_args is not None
    _, params = call_args[0]
    assert params["term"] == r"%100\%\_guvenlik\\test%"
    assert params["author"] == r"%admin\_\%%"



def test_dispatch_search_notes():
    mock_db = MagicMock()
    # 1. Başarılı dispatch
    res = dispatch_tool(mock_db, "search_notes", {"query": "bariyer", "limit": 3})
    assert res.tool == "search_notes"

    # 2. Eksik query parametresi
    err_res = dispatch_tool(mock_db, "search_notes", {"query": ""})
    assert "zorunludur" in (err_res.note or "")


def test_format_narrative_search_notes():
    # 1. Kayıt bulundu
    res_found = ToolResult(
        tool="search_notes",
        params={"query": "VIP"},
        rows=[{"id": 1, "body": "VIP misafir araçları Doğu Otoparkına yönlendirilir."}],
    )
    narrative = format_narrative("search_notes", {"query": "VIP"}, res_found)
    assert "'VIP' ile ilgili 1 adet not bulundu" in narrative

    # 2. Kayıt bulunamadı
    res_empty = ToolResult(
        tool="search_notes",
        params={"query": "helikopter"},
        rows=[],
    )
    narrative_empty = format_narrative("search_notes", {"query": "helikopter"}, res_empty)
    assert "herhangi bir vardiya notu veya prosedür bulunamadı" in narrative_empty
