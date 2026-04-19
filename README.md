# makkuro

### AI に送る前に、機密情報を自動で塗りつぶす。

Claude Code / Codex / Gemini CLI / aider などの AI ツールに、
うっかり **顧客のメールアドレス / 電話番号 / API キー / クレカ番号**
まで一緒に送っていませんか？ makkuro を手元で立ち上げておけば、
AI に届く前に自動でダミー値へ置換し、返ってきた応答は必要に応じて
元の値へ戻します。AI 側のログには個人情報が残りません。

- **設定は 1 回だけ** — `brew install` して環境変数を 1 行通すだけ。
- **ローカル完結** — 塗りつぶしは手元の PC で。追加 SaaS 不要。
- **日本語情報に強い** — 携帯/固定電話、郵便番号、マイナンバー、Luhn 付きクレカ番号を標準サポート。
- **気づきやすい監査ログ** — 「いつ・何の種別を塗った」が JSONL で残る (値そのものは保存しない)。

[![CI](https://github.com/sotanengel/makkuro/actions/workflows/ci.yml/badge.svg)](https://github.com/sotanengel/makkuro/actions/workflows/ci.yml)
[![Security](https://github.com/sotanengel/makkuro/actions/workflows/security.yml/badge.svg)](https://github.com/sotanengel/makkuro/actions/workflows/security.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)

> ⚠️ **Status**: Alpha (0.1.x)。設定キーは 1.0 までに変わる可能性があります。

---

## 30 秒でイメージ

あなたがターミナルに書くのはいつもどおり:

> 田中さん (tanaka@example.com, 090-1234-5678) 向けに謝罪メールの下書きを書いて

makkuro を経由すると、AI に実際に届くのは **こう書き換わったもの**:

> 田中さん (`<MAKKURO_EMAIL_0001>`, `<MAKKURO_JP_MOBILE_0001>`) 向けに謝罪メールの下書きを書いて

AI から返ってきた本文中の `<MAKKURO_EMAIL_0001>` は自動で `tanaka@example.com` に戻るので、
**あなたから見た体験は変わりません**。メール・電話番号・API キー・マイナンバー・クレカ番号などを
一通り標準で検出します。

---

## 今すぐ使う (3 行)

```bash
brew tap sotanengel/makkuro https://github.com/sotanengel/makkuro.git
brew install --HEAD sotanengel/makkuro/makkuro
makkuro start                                   # 別ターミナルで起動しっぱなしに
```

あとは AI CLI 側で環境変数を 1 行通すだけ。例えば Claude Code なら:

```bash
eval "$(makkuro install claude)"   # codex / gemini / aider も同じ要領
claude
```

動作確認だけしたければ AI には投げずに:

```bash
makkuro test "連絡先 foo@example.com / 090-1234-5678 まで"
```

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
- [Takumi Guard (サプライチェーン保護)](#takumi-guard-サプライチェーン保護)
- [開発](#開発)
- [詳しい仕組みとユースケース](#詳しい仕組みとユースケース)
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

## Takumi Guard (サプライチェーン保護)

makkuro は依存を最小限に保ち hash-pin していますが、それでも **新規公開
された悪性パッケージ** が入り込むリスクは残ります。CI では
[GMO Flatt Security の Takumi Guard PyPI プロキシ](https://shisho.dev/docs/ja/t/guard/quickstart/pypi/)
(`https://pypi.flatt.tech/simple/`) 経由で `pip install` を実行し、
既知の悪性リリースが実行される前にブロックしています。

ローカル開発でも同じ保護を有効にしたい場合は、プロジェクト用に以下の
いずれかで opt-in できます。

```bash
# 一時的に (現在のシェルだけ)
export PIP_INDEX_URL=https://pypi.flatt.tech/simple/
export PIP_EXTRA_INDEX_URL=https://pypi.org/simple/
pip install -e ".[dev]"
```

```bash
# このプロジェクト内だけに恒久設定
pip config set --site global.index-url https://pypi.flatt.tech/simple/
pip config set --site global.extra-index-url https://pypi.org/simple/
```

`extra-index-url` を併記しているのは、Takumi Guard 未提供の
新規パッケージ (例: quarantine 期間中) を Upstream PyPI から
フォールバック取得できるようにするためです。完全にブロック優先にしたい
場合は `extra-index-url` を外してください。

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

## 詳しい仕組みとユースケース

### なぜ必要か

AI CLI は手元のコードや会話ログを生のままプロバイダへ送ります。
そこには気付かないうちに以下のような情報が混ざります。

- 社員名簿・顧客連絡先 (メール、電話番号、郵便番号、マイナンバー)
- `.env` の API キー、DB 接続文字列、AWS アクセスキー、GitHub トークン
- クレジットカード番号、社内固有 ID、検証環境のシークレット

一度送信された情報はプロバイダ側のログ・モデル学習・監査トレイルに
残り得ます。組織で AI CLI を広く使わせたいときに、**情報漏洩の不安が
導入のブロッカー** になりがちです。

### 仕組み

手元と AI プロバイダの間にローカル HTTP プロキシを置き、**送信の直前に**
プロンプト本文・MCP tool call・SSE ストリームを走査して、機密値を
placeholder に差し替えます。

```
AI CLI ──► makkuro ──► プロバイダ API
           │   │
           │   └── upstream は allow-list で制約 (それ以外はブロック)
           ├── PII / シークレットを検出 → <MAKKURO_EMAIL_0001> に置換
           ├── マッピングはメモリ or age 暗号化 vault に保持
           └── 応答受信時に必要なら元の値へ rehydrate

[監査ログ]  検出メタデータのみ JSONL に追記 (生の値は記録しない)
```

### Before / After

| Before (直送) | After (makkuro 経由) |
| --- | --- |
| `foo@example.com を CC に入れて` がそのままプロバイダへ | `<MAKKURO_EMAIL_0001> を CC に入れて` に置換されて送信 |
| `.env` を貼り付けると API キー全文が流れる | gitleaks 系パターンで検出 → 置換 or ブロック |
| どのプロンプトで何が流れたか後から追えない | JSONL 監査ログに検出メタデータが残る (値は非保存) |
| CLI の設定ミスで未知のエンドポイントに送られる | upstream allow-list で未登録ホストは即拒否 |
| 開発者が都度手で伏せ字化する運用 | プロキシ経由するだけで自動適用 |

### 向いているユースケース

- **AI CLI を組織に展開したい** — 個々の開発者に注意を促す代わりに、
  プロキシ側で一律に redact してから送る。
- **日本の PII を扱う** — 携帯/固定電話、郵便番号、マイナンバー、
  Luhn 付きクレカ番号などを日本仕様で検出。
- **秘匿前提の検証環境** — ループバックのみ bind、送信先 allow-list、
  Sigstore 署名 + SLSA provenance 付きリリースで
  サプライチェーンを説明可能にしたい。
- **応答を元に戻したい (rehydrate)** — 下書きメールの完成形など、
  実在のデータとして CLI 側に渡したい用途。

### できないこと (非目標)

- **モデル出力そのものの検閲** は行いません。プロンプトに入る前の
  redaction と応答の rehydrate が目的です。
- **完璧な PII 検出を保証しません**。検出はベストエフォートで、toy
  benchmark のマクロ F1 を CI で監視しています。ブロックモードや
  custom_patterns と組み合わせて運用してください。
- **プロバイダ側での保管/学習オプトアウト** は各プロバイダの設定を
  別途行う必要があります。makkuro は "送る前に伏せる" 層です。

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
