## 概要

<!-- この PR で何を・なぜ変えるか 1〜3 文で -->

## 変更内容

<!--
- 主な変更箇所
- 追加/削除した公開 API (あれば)
- 設定キーの追加 (あれば docs/SPEC.md と schema 更新を忘れずに)
-->

## 動作確認

- [ ] `pytest` が通る
- [ ] `ruff check src tests bench scripts` が通る
- [ ] README / CHANGELOG / docs を必要に応じて更新した
- [ ] スキーマを変えた場合は `makkuro policy validate examples/makkuro.toml` で検証した
- [ ] 依存を追加した場合は `python scripts/update_formula.py` で Formula を更新した

## セキュリティ影響

<!--
プロキシ挙動・検出器・allow-list・vault を触る場合は脅威モデル
(docs/SPEC.md §5.7 / §8) との照合結果をメモしてください。
なければ "影響なし" と明記。
-->

## 関連 Issue

<!-- Closes #xxx / Refs #yyy -->
