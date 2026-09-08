"""Gemini client function calling birim testleri (mock ile)."""
from unittest.mock import MagicMock, patch

import pytest

from kervansaray.llm import gemini_client


def test_gemini_missing_key():
    with patch("kervansaray.llm.gemini_client.settings.GEMINI_API_KEY", ""):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY eksik"):
            gemini_client.generate("merhaba")


def test_gemini_text_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Otoparkta su an 12 arac var."}]
                }
            }
        ]
    }
    with patch("kervansaray.llm.gemini_client.settings.GEMINI_API_KEY", "test-key"), \
         patch("kervansaray.llm.gemini_client._session") as mock_session_fn:
        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp
        mock_session_fn.return_value = mock_session

        res = gemini_client.generate("otoparkta kac arac var?")
        assert res["response"] == "Otoparkta su an 12 arac var."
        assert res["function_call"] is None
        assert res["provider"] == "gemini"


def test_gemini_function_call_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "occupancy",
                                "args": {},
                            }
                        }
                    ]
                }
            }
        ]
    }
    with patch("kervansaray.llm.gemini_client.settings.GEMINI_API_KEY", "test-key"), \
         patch("kervansaray.llm.gemini_client._session") as mock_session_fn:
        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp
        mock_session_fn.return_value = mock_session

        tool_decl = [
            {"name": "occupancy", "description": "doluluk", "parameters": {"type": "object"}}
        ]
        res = gemini_client.generate("su an kac arac var?", tools=tool_decl)
        assert res["response"] is None
        assert res["function_call"] == {"name": "occupancy", "args": {}}
        assert res["provider"] == "gemini"
