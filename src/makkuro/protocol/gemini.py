"""Google Gemini adapter (generateContent, non-streaming).

Docs: https://ai.google.dev/api/generate-content

Request body shape::

    {
      "systemInstruction": {"parts": [{"text": "..."}]},  # optional
      "contents": [
        {"role": "user" | "model",
         "parts": [{"text": "..."}, ...]},
        ...
      ],
      ...
    }

Response body::

    {
      "candidates": [
        {"content": {"role": "model", "parts": [{"text": "..."}, ...]}, ...},
        ...
      ],
      ...
    }
"""

from __future__ import annotations

from typing import Any

from makkuro.protocol.base import CanonicalMessage, CanonicalRequest, ContentBlock


def _parts_text(parts: Any) -> list[str]:
    if not isinstance(parts, list):
        return []
    out: list[str] = []
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            out.append(p["text"])
    return out


class GeminiAdapter:
    name = "gemini"
    upstream_path_prefixes = ("/v1beta/models", "/v1/models")

    def decode_request(self, body: dict[str, Any]) -> CanonicalRequest:
        system_inst = body.get("systemInstruction")
        system: str | None = None
        if isinstance(system_inst, dict):
            parts = _parts_text(system_inst.get("parts"))
            if parts:
                system = "\n".join(parts)

        contents_in = body.get("contents") or []
        messages: list[CanonicalMessage] = []
        for c in contents_in:
            if not isinstance(c, dict):
                continue
            role = str(c.get("role", "user"))
            texts = _parts_text(c.get("parts"))
            blocks = [ContentBlock(type="text", text=t) for t in texts]
            messages.append(CanonicalMessage(role=role, content_blocks=blocks))
        return CanonicalRequest(system=system, messages=messages, extra={})

    def encode_request(
        self, canonical: CanonicalRequest, original: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(original)
        if canonical.system is not None:
            out["systemInstruction"] = {"parts": [{"text": canonical.system}]}
        elif "systemInstruction" in out:
            del out["systemInstruction"]

        new_contents: list[dict[str, Any]] = []
        for cm in canonical.messages:
            texts = [b.text or "" for b in cm.content_blocks if b.type == "text"]
            new_contents.append(
                {
                    "role": cm.role,
                    "parts": [{"text": t} for t in texts],
                }
            )
        out["contents"] = new_contents
        return out

    def extract_response_text(
        self, body: dict[str, Any]
    ) -> list[tuple[list[str | int], str]]:
        out: list[tuple[list[str | int], str]] = []
        candidates = body.get("candidates")
        if not isinstance(candidates, list):
            return out
        for i, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                continue
            content = cand.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for j, p in enumerate(parts):
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    out.append(
                        (["candidates", i, "content", "parts", j, "text"], p["text"])
                    )
        return out

    def apply_response_text(
        self, body: dict[str, Any], edits: list[tuple[list[str | int], str]]
    ) -> dict[str, Any]:
        for path, new_text in edits:
            cursor: Any = body
            for step in path[:-1]:
                cursor = cursor[step]
            cursor[path[-1]] = new_text
        return body
