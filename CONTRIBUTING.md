# Contributing to makkuro

ありがとうございます。makkuro に関心を持っていただいて嬉しいです。
本ドキュメントは **貢献者が最短でマージ可能な PR を出せる** ための
最小ガイドです。困ったら Issue で気軽に聞いてください。

## 行動規範

このプロジェクトは [Contributor Covenant v2.1](CODE_OF_CONDUCT.md) を
採用しています。参加されるすべての方はこれを尊重してください。

## セキュリティ脆弱性の報告

公開 Issue ではなく **GitHub Security Advisory** 経由で非公開に報告
してください。詳細は [SECURITY.md](SECURITY.md) を参照。

## 開発環境のセットアップ

Python 3.11 以上が必要です。

```bash
git clone https://github.com/sotanengel/makkuro.git
cd makkuro
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest           # 109本 ほど
ruff check src tests bench scripts
```

## ブランチ / PR の流れ

1. `main` から作業ブランチを切る (`feat/<短い名前>` / `fix/<短い名前>` 推奨)。
2. 小さな単位でコミット。コミットメッセージは [Conventional
   Commits](https://www.conventionalcommits.org/) に寄せています
   (`feat(pipeline): ...`, `fix(proxy): ...` 等)。
3. PR を出すときは以下を確認:
   - `pytest` と `ruff check` がローカルで通る
   - 挙動を変える変更にはテストを追加
   - スキーマを増やした場合は `src/makkuro/schema/makkuro.schema.json` も更新
   - Homebrew Formula に影響する依存変更なら `python scripts/update_formula.py`
   - 公開 API / 設定キーを変える場合は `docs/SPEC.md` に反映

## テストのポリシー

- ユニットは `tests/` 直下。ファイル名は `test_<対象モジュール>.py`。
- ネットワーク・時刻・ファイルシステムに依存しないこと。必要なら
  `tmp_path` / `monkeypatch` を使う。
- プロキシ挙動テストは httpx / Starlette の TestClient を使用し、
  upstream を fake でモックする。

## コーディング規約

- `ruff` の設定 (`pyproject.toml`) が一次情報。line-length = 100。
- 型ヒント必須。`from __future__ import annotations` をファイル先頭に。
- モジュール公開 API は `__all__` を書くか、`_` 接頭辞で private を示す。
- コメントは *WHY* のみ。*WHAT* はコードと命名で表現する。

## 検出器の追加

新しい検出器を入れる場合:

1. `src/makkuro/detectors/` に実装 (`Detector` を継承)。
2. `DEFAULT_DETECTORS` に追加。
3. `tests/test_detectors.py` か専用ファイルに単体テスト。
4. `bench/data/toy/samples.json` にサンプルを追加し、`python -m
   bench.run_eval bench/data/toy/samples.json` で F1 を確認。
5. README の検出器表も更新。

## リリース (メンテナ向け)

1. `pyproject.toml` の `version` と `src/makkuro/__init__.py` の
   `__version__` を bump (例: `0.1.0` → `0.1.1`)。
2. `CHANGELOG.md` に該当バージョンのエントリを追記。
3. 署名タグ `git tag -s vX.Y.Z -m "vX.Y.Z"` を push。
4. `.github/workflows/release.yml` が以下を自動で実行:
   - sdist / wheel ビルド (reproducible)
   - CycloneDX SBOM 生成
   - Sigstore 署名 + SLSA provenance
   - PyPI Trusted Publishing (OIDC, 手動承認ゲート付き)
   - Homebrew Formula の `url` / `sha256` 書き換え → main へ push
   - GitHub Release 作成

## 質問 / 議論

機能提案や仕様相談は GitHub Discussions、または Issue (label: `question`
/ `enhancement`) にどうぞ。
