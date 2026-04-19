from __future__ import annotations

from makkuro.protocol import GeminiAdapter


class TestGeminiAdapter:
    def test_round_trip(self):
        adapter = GeminiAdapter()
        body = {
            "systemInstruction": {"parts": [{"text": "be helpful"}]},
            "contents": [
                {"role": "user", "parts": [{"text": "hello"}]},
                {"role": "model", "parts": [{"text": "hi"}]},
            ],
        }
        canonical = adapter.decode_request(body)
        assert canonical.system == "be helpful"
        assert canonical.messages[0].content_blocks[0].text == "hello"
        assert canonical.messages[1].content_blocks[0].text == "hi"

        canonical.messages[0].content_blocks[0].text = "REDACTED"
        out = adapter.encode_request(canonical, body)
        assert out["contents"][0]["parts"][0]["text"] == "REDACTED"
        assert out["systemInstruction"] == {"parts": [{"text": "be helpful"}]}

    def test_response_extract_apply(self):
        adapter = GeminiAdapter()
        body = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "a"}, {"text": "b"}],
                    }
                }
            ]
        }
        edits = adapter.extract_response_text(body)
        assert len(edits) == 2
        new_edits = [(p, t.upper()) for p, t in edits]
        adapter.apply_response_text(body, new_edits)
        parts = body["candidates"][0]["content"]["parts"]
        assert parts[0]["text"] == "A"
        assert parts[1]["text"] == "B"
