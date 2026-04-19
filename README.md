# makkuro

**AI CLI 向けローカル redaction プロキシ**

makkuro は AI CLI (Claude Code, Codex CLI, Gemini CLI, aider など) と
AI プロバイダ API の間にローカル HTTP プロキシを立て、送信前に機密情報を
placeholder 化し、応答受信時に必要なら復元する Python 製ツールです。

- ライセンス: Apache-2.0
- 対応 Python: 3.11+
- ステータス: 開発中 (Phase 0 — baseline detectors & toy benchmark)

## Phase 0 で使えるもの

```bash
# dev install
pip install -e .

# 検出の動作確認
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

HTTP プロキシ、age vault、audit log、OpenAI/Gemini adapters は Phase 1 以降で実装します。

詳細は [`docs/SPEC.md`](docs/SPEC.md) を参照してください。
