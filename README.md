# makkuro

**AI CLI 向けローカル redaction プロキシ**

makkuro は AI CLI (Claude Code, Codex CLI, Gemini CLI, aider など) と
AI プロバイダ API の間にローカル HTTP プロキシを立て、送信前に機密情報を
placeholder 化し、応答受信時に必要なら復元する Python 製ツールです。

- ライセンス: Apache-2.0
- 対応 Python: 3.11+
- ステータス: 開発中 (Phase 0)

詳細仕様は `docs/SPEC.md` を参照してください。
