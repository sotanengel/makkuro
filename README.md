# makkuro

**AI CLI 向けローカル redaction プロキシ**

makkuro は AI CLI (Claude Code, Codex CLI, Gemini CLI, aider など) と
AI プロバイダ API の間にローカル HTTP プロキシを立て、送信前に機密情報を
placeholder 化し、応答受信時に必要なら復元する Python 製ツールです。

- ライセンス: Apache-2.0
- 対応 Python: 3.11+
- ステータス: 開発中 (Phase 1 — Anthropic Messages API プロキシ)

## 使い方

```bash
# dev install
pip install -e .

# プロキシを起動 (127.0.0.1:8787)
makkuro start

# 別ターミナルから Claude Code 等に環境変数を設定
eval "$(makkuro install claude)"
# or: export ANTHROPIC_BASE_URL=http://127.0.0.1:8787

# 検出の動作確認 (dry-run)
makkuro test "連絡先 foo@example.com / 090-1234-5678 まで"

# ベースライン検出器のリスト
makkuro doctor

# toy benchmark (マクロ F1 を算出)
PYTHONPATH=src:. python -m bench.run_eval bench/data/toy/samples.json
```

Phase 0 で実装されている検出器:

| 種別            | 実装        | メモ                              |
| ------------- | --------- | ------------------------------- |
| EMAIL         | regex     | 多言語セパレータ許容                      |
| JP_MOBILE     | regex     | 070/080/090 系、ハイフン／スペース／連続桁すべて可 |
| JP_LANDLINE   | regex     | 10 桁制約、携帯プレフィックス除外              |
| JP_ZIP        | regex     | `〒?NNN-NNNN`                    |
| JP_CREDIT_CARD| Luhn      | 13–19 桁、Luhn 通過のみ               |
| JP_MYNUMBER   | checksum  | 12 桁、公式チェックデジット検証               |

Phase 1 時点での対応プロバイダ:

- **Anthropic Messages API** (`POST /v1/messages`, 非ストリーミング)

Phase 2 以降で追加予定:
- age 暗号化 vault、JSONL 監査ログ
- OpenAI / Gemini / OpenAI 互換エンドポイント
- SSE ストリーミング、MCP tool_use / tool_result の deep-redact

詳細は [`docs/SPEC.md`](docs/SPEC.md) を参照してください。
