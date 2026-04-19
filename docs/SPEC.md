# makkuro 総合仕様書 v1.0

> **AI CLI 向けローカル redaction プロキシ**
> このドキュメントは生成AI エージェント (Claude Code 等) が実装を進めるための **自己完結した仕様** です。

**版**: 1.0（統合版）
**更新**: 2026-04-19
**ライセンス**: Apache-2.0
**想定言語**: Python 3.11+

本ファイルは PR で最初に合意した仕様を固定したスナップショットです。
今後の仕様変更は `## 変更履歴` と Pull Request のリンクで追跡します。
製品名は当初 `kurosaku` でしたが、リポジトリ名に合わせて **`makkuro`** に統一しました。
それに伴い以下も一括で変更されています:

- パッケージ名 / CLI コマンド: `kurosaku` → `makkuro`
- 環境変数 prefix: `KUROSAKU_*` → `MAKKURO_*`
- 設定ファイル: `.kurosaku.toml` → `.makkuro.toml`
- Placeholder 形式: `<KUROSAKU_...>` → `<MAKKURO_...>`
- XDG パス: `$XDG_*/kurosaku/` → `$XDG_*/makkuro/`

以下、本書中の旧名称は読み替えてください（将来的に機械的に置換する予定）。

---

(※ 本文は design doc に従い追って補完予定。Phase 0 段階では §4.F2, §4.F3, §7,
§10 Phase 0 の要件が実装対象です。)
