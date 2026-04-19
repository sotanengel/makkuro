from __future__ import annotations

from makkuro.protocol import AnthropicAdapter


class TestAnthropicAdapter:
    def test_string_content_round_trip(self):
        adapter = AnthropicAdapter()
        body = {
            "model": "m",
            "messages": [{"role": "user", "content": "hello"}],
        }
        canonical = adapter.decode_request(body)
        assert canonical.messages[0].content_blocks[0].text == "hello"
        out = adapter.encode_request(canonical, body)
        assert out["messages"][0]["content"] == [{"type": "text", "text": "hello"}]

    def test_structured_content_round_trip(self):
        adapter = AnthropicAdapter()
        body = {
            "model": "m",
            "system": "be helpful",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "a"},
                        {"type": "text", "text": "b"},
                    ],
                }
            ],
        }
        canonical = adapter.decode_request(body)
        assert canonical.system == "be helpful"
        texts = [b.text for b in canonical.messages[0].content_blocks]
        assert texts == ["a", "b"]
        out = adapter.encode_request(canonical, body)
        assert out["messages"][0]["content"][0]["text"] == "a"
        assert out["messages"][0]["content"][1]["text"] == "b"

    def test_tool_use_passthrough(self):
        adapter = AnthropicAdapter()
        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tu_1",
                            "name": "lookup",
                            "input": {"q": "secret@example.com"},
                        }
                    ],
                }
            ]
        }
        canonical = adapter.decode_request(body)
        tu = canonical.messages[0].content_blocks[0]
        assert tu.type == "tool_use"
        assert tu.tool_name == "lookup"
        assert tu.tool_input == {"q": "secret@example.com"}
        out = adapter.encode_request(canonical, body)
        assert out["messages"][0]["content"][0]["name"] == "lookup"
        assert out["messages"][0]["content"][0]["input"] == {"q": "secret@example.com"}

    def test_response_text_extract_and_apply(self):
        adapter = AnthropicAdapter()
        body = {
            "content": [
                {"type": "text", "text": "alpha"},
                {"type": "tool_use", "name": "foo"},
                {"type": "text", "text": "beta"},
            ]
        }
        edits = adapter.extract_response_text(body)
        assert len(edits) == 2
        # Replace texts
        new_edits = [(path, text.upper()) for path, text in edits]
        adapter.apply_response_text(body, new_edits)
        assert body["content"][0]["text"] == "ALPHA"
        assert body["content"][2]["text"] == "BETA"
