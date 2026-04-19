from __future__ import annotations

from makkuro.protocol import OpenAIAdapter


class TestOpenAIAdapter:
    def test_string_content_round_trip(self):
        adapter = OpenAIAdapter()
        body = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "be helpful"},
                {"role": "user", "content": "hello"},
            ],
        }
        canonical = adapter.decode_request(body)
        assert canonical.system == "be helpful"
        assert canonical.messages[0].role == "user"
        assert canonical.messages[0].content_blocks[0].text == "hello"

        # Edit and re-encode.
        canonical.messages[0].content_blocks[0].text = "HELLO"
        out = adapter.encode_request(canonical, body)
        assert out["messages"][0]["role"] == "system"
        assert out["messages"][0]["content"] == "be helpful"
        assert out["messages"][1]["content"] == "HELLO"

    def test_structured_content_preserved(self):
        adapter = OpenAIAdapter()
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "a"},
                        {"type": "text", "text": "b"},
                    ],
                }
            ]
        }
        canonical = adapter.decode_request(body)
        texts = [b.text for b in canonical.messages[0].content_blocks]
        assert texts == ["a", "b"]
        out = adapter.encode_request(canonical, body)
        # The outbound content should remain a list when the inbound was a list.
        assert isinstance(out["messages"][0]["content"], list)

    def test_extract_apply_response_string(self):
        adapter = OpenAIAdapter()
        body = {
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "hello"}}
            ]
        }
        edits = adapter.extract_response_text(body)
        assert edits == [(["choices", 0, "message", "content"], "hello")]
        new_edits = [(path, text.upper()) for path, text in edits]
        adapter.apply_response_text(body, new_edits)
        assert body["choices"][0]["message"]["content"] == "HELLO"
