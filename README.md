# makkuro

**AI CLI 向けローカル redaction プロキシ**

[![CI](https://github.com/sotanengel/makkuro/actions/workflows/ci.yml/badge.svg)](https://github.com/sotanengel/makkuro/actions/workflows/ci.yml)
[![Security](https://github.com/sotanengel/makkuro/actions/workflows/security.yml/badge.svg)](https://github.com/sotanengel/makkuro/actions/workflows/security.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)

makkuro は Claude Code / Codex CLI / Gemini CLI / aider などの AI CLI と
AI プロバイダ API の間にローカル HTTP プロキシを立てるツールです。

- 送信前にプロンプトから **PII / シークレットを検出** し、placeholder
  (例: `<MAKKURO_EMAIL_0001>`) に置換します。
- 応答受信時に必要なら元の値へ **rehydrate** します。
- 送信先は **allow-list で厳格に制約** され、ループバック以外からは受けません。
- ローカル完結・追加 SaaS 不要・Apache-2.0。

> ⚠️ **Status**: Alpha (0.1.x). API / 設定キーは 1.0 までに変わる可能性があります。
> プロダクションで使う前に [SECURITY.md](SECURITY.md) と
> [docs/SPEC.md](docs/SPEC.md) の脅威モデルを確認してください。

---

## 目次

- [インストール](#インストール)
- [クイックスタート](#クイックスタート)
- [設定ファイル](#設定ファイル)
- [CLI リファレンス](#cli-リファレンス)
- [検出器](#検出器)
- [対応プロバイダ](#対応プロバイダ)
- [カスタムパターンと allow-list](#カスタムパターンと-allow-list)
- [監査ログ](#監査ログ)
- [暗号化 vault (任意)](#暗号化-vault-任意)
- [ベンチマーク](#ベンチマーク)
- [開発](#開発)
- [セキュリティ](#セキュリティ)
- [ライセンス](#ライセンス)

---

## インストール

### Homebrew (macOS / Linuxbrew, 推奨)

```bash
# 1) tap を追加 (最初の1回だけ)
brew tap sotanengel/makkuro https://github.com/sotanengel/makkuro.git

# 2) 安定版リリースからインストール
brew install makkuro

# あるいは main ブランチ HEAD から直接
brew install --HEAD sotanengel/makkuro/makkuro
```

`python@3.13` を自動で取得し、依存は隔離された virtualenv に入ります。
Formula は [`Formula/makkuro.rb`](Formula/makkuro.rb) にあり、リリース
ワークフローが tag 時に `url` / `sha256` を更新します。

### pip

Python 3.11 以上が必要です。

```bash
# 通常インストール (メモリ vault 使用)
pip install makkuro

# 永続 age 暗号化 vault を使う場合
pip install "makkuro[age]"
```

開発用の `pip install -e ".[dev]"` も利用できます。詳細は
[CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

---

## クイックスタート

Claude Code を例に、3 コマンドで動作確認できます。

```bash
# 1. プロキシを起動 (127.0.0.1:8787)
makkuro start

# 2. 別ターミナルで環境変数をセットしてから AI CLI を起動
eval "$(makkuro install claude)"
claude   # or: codex / aider / etc.

# 3. 検出の動作確認 (AI には投げずローカルで dry-run)
makkuro test "連絡先 foo@example.com / 090-1234-5678 まで"
```

`makkuro test` の出力例:

```json
{
  "input": "連絡先 foo@example.com / 090-1234-5678 まで",
  "redacted": "連絡先 <MAKKURO_EMAIL_0001> / <MAKKURO_JP_MOBILE_0001> まで",
  "detections": [
    {"type": "EMAIL",     "start": 3,  "end": 18, "detector": "regex:email"},
    {"type": "JP_MOBILE", "start": 21, "end": 34, "detector": "regex:jp_mobile"}
  ]
}
```

他の CLI 用 env スニペットは `makkuro install codex | gemini | aider` で出力できます。

---

## 設定ファイル

makkuro はデフォルト値で動きますが、細かな挙動は TOML で上書きできます。
既定の探索順は以下です (先に見つかったものが採用されます):

1. `--config` で指定したパス
2. `./.makkuro.toml`
3. `$XDG_CONFIG_HOME/makkuro/config.toml`
4. `~/.config/makkuro/config.toml`

テンプレートは [`examples/makkuro.toml`](examples/makkuro.toml) にあります。
配置したら次のコマンドでスキーマ検証できます:

```bash
makkuro policy validate .makkuro.toml
```

最小例:

```toml
schema_version = 1

[proxy]
port = 8787
bind = "127.0.0.1"        # ループバック以外にしたい場合は MAKKURO_ALLOW_PUBLIC_BIND=1 が必要

[redaction]
mode = "mask"             # mask | block | warn
rehydrate = true

[audit]
enabled = true
# path = "/var/log/makkuro/audit.jsonl"  # 省略時は $XDG_STATE_HOME/makkuro/audit.jsonl
```

環境変数による上書きも可能です: `MAKKURO_PORT`, `MAKKURO_BIND`,
`MAKKURO_NO_REHYDRATE`。

---

## CLI リファレンス

| コマンド | 役割 |
| --- | --- |
| `makkuro start [--config P] [--port N] [--bind H]` | プロキシを foreground で起動 |
| `makkuro install <claude\|codex\|gemini\|aider> [--port N]` | 各 AI CLI 用 env スニペットを出力 |
| `makkuro test "<text>"` | 検出器を dry-run し JSON で結果出力 |
| `makkuro doctor [--config P]` | 読み込まれた設定と有効な検出器を表示 |
| `makkuro policy validate <file>` | TOML 設定を同梱スキーマで検証 |
| `makkuro audit tail <file> [-n N]` | 監査ログ末尾 N 行を表示 |
| `makkuro verify` | インストール済みパッケージの自己整合性チェック (SC-7) |
| `makkuro version` | バージョン表示 |

---

## 検出器

デフォルトで有効な検出器:

| 種別 | 実装 | メモ |
| --- | --- | --- |
| EMAIL | regex | 多言語セパレータ許容 |
| JP_MOBILE | regex | 070/080/090 系、ハイフン／スペース／連続桁すべて可 |
| JP_LANDLINE | regex | 10 桁制約、携帯プレフィックス除外 |
| JP_ZIP | regex | `〒?NNN-NNNN` |
| JP_CREDIT_CARD | Luhn | 13–19 桁、Luhn 通過のみ |
| JP_MYNUMBER | checksum | 12 桁、公式チェックデジット検証 |
| SECRETS | gitleaks 系 | API key / token / credential |

有効な検出器一覧は `makkuro doctor` で確認できます。

---

## 対応プロバイダ

| プロバイダ | プロトコル | streaming (SSE) | MCP deep-redact |
| --- | --- | --- | --- |
| Anthropic (`api.anthropic.com`) | `anthropic` | ✅ | ✅ |
| OpenAI (`api.openai.com`) | `openai` | ✅ | ✅ |
| Google Gemini (`generativelanguage.googleapis.com`) | `gemini` | ✅ | ✅ |

それぞれの upstream は `[providers]` テーブルで差し替え可能です (OpenAI 互換
エンドポイントなどを想定)。送信先は **allow-list で厳格チェック** されるため、
未登録ホストへは一切プロキシされません。

---

## カスタムパターンと allow-list

ユーザ定義の追加パターンと、検出しても **マスクしない** 例外語リストを
TOML で指定できます。

```toml
[redaction.custom_patterns]
# 名前 = 正規表現
EMPLOYEE_ID = "EMP-[0-9]{6}"

[redaction.allow_list]
# type -> リテラル値のリスト (これらは検出しても redact しない)
EMAIL = ["press@example.com"]
```

---

## 監査ログ

デフォルトで JSONL 形式の監査ログを出力します (検出 **メタデータのみ**。
検出した生の値は書き込みません)。末尾を確認するには:

```bash
makkuro audit tail "$XDG_STATE_HOME/makkuro/audit.jsonl" -n 50
```

出力先は `[audit].path` で変更できます。`enabled = false` で完全停止。

---

## 暗号化 vault (任意)

placeholder ↔ 元値のマッピングは既定で **メモリ上にのみ保持** され、
プロキシ終了と共に消えます。セッションを跨いで保持したい場合は `age`
暗号化 vault を利用できます:

```bash
pip install "makkuro[age]"
```

```toml
[vault]
backend = "age"
path = "~/.local/share/makkuro/vault.age"
identity_path = "~/.config/makkuro/age.key"
purge_after_days = 7
```

---

## ベンチマーク

同梱の toy データセットでマクロ F1 を測れます:

```bash
PYTHONPATH=src:. python -m bench.run_eval bench/data/toy/samples.json
```

---

## 開発

```bash
git clone https://github.com/sotanengel/makkuro.git
cd makkuro
pip install -e ".[dev]"
pytest
ruff check src tests bench
```

貢献ガイドラインは [CONTRIBUTING.md](CONTRIBUTING.md)、
コミュニティ規範は [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) を参照してください。

---

## セキュリティ

脆弱性の報告手順とサプライチェーン方針は [SECURITY.md](SECURITY.md) を参照。
公開 Issue ではなく GitHub Security Advisory 経由でお願いします。

- PyPI Trusted Publishing (OIDC) でリリース
- wheel / sdist は Sigstore で署名 + SLSA provenance 添付
- CycloneDX SBOM をリリースに添付
- `makkuro verify` でインストール済みハッシュを同梱マニフェストと照合可能

---

## ライセンス

Apache-2.0. 詳細は [LICENSE](LICENSE) を参照してください。
