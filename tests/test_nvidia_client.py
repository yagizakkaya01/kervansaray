"""NVIDIA NIM (Nemotron 3.5 Lightning) istemci birim testleri."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kervansaray.config import settings
from kervansaray.llm import nvidia_client
from kervansaray.tools.schemas import OPENAI_TOOLS


def test_nvidia_available() -> None:
    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-test123"):
        assert nvidia_client.available() is True
    with patch.object(settings, "NVIDIA_API_KEY", ""):
        assert nvidia_client.available() is False


def test_nvidia_generate_tool_call() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "vehicle_history",
                                "arguments": '{"plate": "06 AK 0052"}',
                            },
                        }
                    ],
                }
            }
        ]
    }

    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-test123"), \
         patch("requests.Session.post", return_value=mock_resp):
        res = nvidia_client.generate("06 AK 0052 geçmişi", tools=OPENAI_TOOLS)

    assert res["provider"] == "nvidia"
    assert "function_call" in res
    assert res["function_call"]["name"] == "vehicle_history"
    assert res["function_call"]["args"] == {"plate": "06 AK 0052"}


def test_nvidia_generate_direct_text() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Bu soru sistem kapsamı dışındadır.",
                }
            }
        ]
    }

    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-test123"), \
         patch("requests.Session.post", return_value=mock_resp):
        res = nvidia_client.generate("Hava nasıl?")

    assert res["provider"] == "nvidia"
    assert res["response"] == "Bu soru sistem kapsamı dışındadır."


def test_nvidia_generate_error() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch.object(settings, "NVIDIA_API_KEY", "nvapi-test123"), \
         patch("requests.Session.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="NVIDIA 429"):
            nvidia_client.generate("test")
