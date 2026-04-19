# makkuro 総合仕様書

> **AI CLI 向けローカル redaction プロキシ**
> このドキュメントは実装判断が必要な局面で参照する一次仕様です。
> 変更は PR のリンクと `## 変更履歴` で追跡します。

**版**: 1.0 (alpha スナップショット)
**更新**: 2026-04-19
**ライセンス**: Apache-2.0
**対応 Python**: 3.11+

## 1. スコープと非目標

### 1.1 目標

- AI CLI (Claude Code / Codex / Gemini CLI / aider 等) と AI
  プロバイダ API の間に置き、**送信直前に** PII / シークレットを
  検出して placeholder へ置換する。
- プロバイダ応答中の placeholder を元の値へ **rehydrate** して、
  CLI 側の UX を壊さない。
- upstream を **allow-list で厳格制約** し、未登録ホストは拒否。
- ローカル完結・ループバック bind 既定・追加 SaaS 不要。

### 1.2 非目標

- モデル出力そのものの検閲 / モデレーションは行わない。
- 完璧な PII 検出は保証しない (best-effort; F1 を toy benchmark で継続監視)。
- プロバイダ側の保管 / 学習オプトアウトは各プロバイダ設定の責務。
- 法令遵守 (GDPR / APPI / HIPAA 等) の代替にはならない。補助層。

## 2. アーキテクチャ

```
[AI CLI] ──► [makkuro (loopback HTTP)] ──► [プロバイダ API (allow-list)]
                │
                ├─ protocol adapter (anthropic / openai / gemini)
                │   └─ canonical message に正規化
                ├─ detector pipeline (regex / checksum / gitleaks)
                │   └─ allow_list / custom_patterns 適用
                ├─ placeholder mint & vault (memory / age)
                │   └─ placeholder ↔ 原値マッピング
                ├─ response rehydrator (non-streaming + SSE look-back)
                └─ audit (JSONL, 値は保存しない)
```

主要モジュール (`src/makkuro/`):

| モジュール | 役割 |
| --- | --- |
| `proxy/app.py` | Starlette ASGI アプリ構築 |
| `proxy/server.py` | uvicorn ランナ (loopback 強制) |
| `proxy/redactor.py` | リクエスト/応答の正規化 + 検出 + 置換 |
| `proxy/sse.py` | SSE チャンク境界を跨ぐ look-back 再水和 |
| `proxy/egress.py` | allow-list チェック付き httpx クライアント |
| `protocol/*.py` | Anthropic / OpenAI / Gemini アダプタ |
| `detectors/*.py` | 個別検出器と `DEFAULT_DETECTORS` |
| `pipeline.py` | 検出器をまとめて走らせる |
| `placeholder.py` | placeholder 生成 + 置換ロジック |
| `vault/*.py` | memory / age / (予約) keychain |
| `audit.py` | JSONL ローテーション書き込み |
| `integrity.py` | リリース後の自己整合性チェック (SC-7) |
| `config.py` / `policy.py` | TOML ロード + JSON Schema 検証 |
| `cli.py` | `makkuro` サブコマンド |

## 3. データモデル

### 3.1 Detection

```python
@dataclass
class Detection:
    type: str         # "EMAIL" / "JP_MOBILE" / ...
    start: int        # 文字列上のオフセット (入力原文基準)
    end: int
    score: float      # 0.0〜1.0
    detector: str     # "regex:email" / "luhn" / ...
    value: str        # 元の値
```

### 3.2 Placeholder

- 形式: `<MAKKURO_<TYPE>_<4桁連番>>`
- 例: `<MAKKURO_EMAIL_0001>`
- 1プロセス内で安定 (同じ値は同じ placeholder)。
- age vault を使う場合はセッション跨ぎで安定。

## 4. 検出器

### 4.1 デフォルト検出器

| 種別 | 実装 | 備考 |
| --- | --- | --- |
| `EMAIL` | regex | 多言語セパレータ許容 |
| `JP_MOBILE` | regex | 070/080/090 系、ハイフン/スペース/連続桁 |
| `JP_LANDLINE` | regex | 10 桁、携帯プレフィックス除外 |
| `JP_ZIP` | regex | `〒?NNN-NNNN` |
| `JP_CREDIT_CARD` | Luhn | 13–19 桁、Luhn 通過のみ |
| `JP_MYNUMBER` | checksum | 12 桁、公式チェックデジット |
| `SECRETS` | gitleaks 系パターン | API キー / token |

### 4.2 ユーザ定義拡張

- `redaction.custom_patterns` (TOML): 名前 → Python regex。名前が
  そのまま placeholder の TYPE になる。
- `redaction.allow_list` (TOML): TYPE → リテラル値の配列。検出後に
  リストと一致したら redact せずに通す。

## 5. プロトコル / プロバイダ

### 5.1 対応マトリクス

| プロバイダ | protocol key | 非ストリーミング | SSE | MCP deep-redact |
| --- | --- | --- | --- | --- |
| Anthropic | `anthropic` | ✅ | ✅ | ✅ |
| OpenAI | `openai` | ✅ | ✅ | ✅ |
| Google Gemini | `gemini` | ✅ | ✅ | ✅ |

### 5.2 canonical message

各 adapter はプロバイダ固有フォーマットを `CanonicalMessage`
(`protocol/base.py`) に正規化して、共通の redactor に渡す。
応答経路は逆向きに変換。

### 5.3 MCP deep-redact

MCP `tool_use` / `tool_result` ペイロードを再帰的に走査し、文字列
フィールドに対して同じ検出器を適用する。

## 6. ストリーミング (SSE)

- チャンク境界で placeholder が分断される可能性があるため、
  `proxy/sse.py` は直前 N バイトをバッファに保持 (既定 512B、
  `experimental.streaming_buffer_bytes` で上書き)。
- rehydrate は境界を跨いでマッチした時点で一括実施。

## 7. 監査

- JSONL、1 行 1 イベント。
- 既定パス: `$XDG_STATE_HOME/makkuro/audit.jsonl`。
- 各イベントに **検出メタデータのみ** を書く (`type`, `detector`,
  `start`, `end`, `score`)。**値 (value) は書かない**。
- `makkuro audit tail <path> -n N` で末尾表示。

## 8. 脅威モデル (要点)

| # | 脅威 | 緩和 |
| --- | --- | --- |
| T1 | AI CLI が生 PII を送る | 送信直前に検出→placeholder 化 |
| T2 | 未登録ホストへ流出 | `security.network_allowlist_strict = true` + upstream チェック |
| T3 | 検出漏れ | ブロックモード / custom_patterns / toy benchmark の継続監視 |
| T4 | 応答への placeholder 残り | SSE look-back、rehydrate トグル |
| T5 | vault の永続化でディスク漏洩 | 既定 memory、age 暗号化が必要ならオプトイン |
| T6 | 監査ログ自体に値が漏れる | イベントに値を書かない仕様 |
| T7 | 配布物の改ざん | Sigstore 署名 + SLSA provenance + `makkuro verify` |
| T8 | 依存パッケージの CVE | 日次 pip-audit + osv-scanner、72h SLA (SC-1.5/6/11) |

## 9. 設定スキーマ

一次情報は `src/makkuro/schema/makkuro.schema.json`。サンプルは
`examples/makkuro.toml`。以下は節単位の概要。

| 節 | 主なキー |
| --- | --- |
| `proxy` | `port`, `bind`, `request_timeout_sec`, `max_body_mb` |
| `redaction` | `mode` (mask/block/warn), `rehydrate`, `custom_patterns`, `allow_list` |
| `providers.<name>` | `upstream`, `protocol`, `enabled` |
| `security` | `network_allowlist_strict`, `integrity_check` |
| `audit` | `enabled`, `path`, `level` |
| `vault` | `backend` (memory/age/keychain), `path`, `identity_path`, `purge_after_days` |
| `telemetry` | `metrics_bind`, `otel_*` |
| `experimental` | `mcp_deep_redact`, `streaming_buffer_bytes`, `prompt_cache_safe_mode` |

環境変数上書き: `MAKKURO_PORT`, `MAKKURO_BIND`, `MAKKURO_NO_REHYDRATE`,
`MAKKURO_ALLOW_PUBLIC_BIND`。

## 10. フェーズマップ (実装ステータス)

| Phase | 内容 | 状態 |
| --- | --- | --- |
| 0 | スキャフォールド + 基本検出器 + toy benchmark | ✅ |
| 1 | プロキシ + Anthropic 非ストリーミング | ✅ |
| 2 | OpenAI / Gemini 追加 + 監査 + 検証 | ✅ |
| 3 | MCP deep-redact + secrets | ✅ |
| 4 | custom_patterns / allow_list | ✅ |
| 5 | SSE streaming | ✅ |
| 6 | 署名 / SBOM / Trusted Publishing | ✅ |
| 7 | age 永続 vault | ✅ |
| 8 | JP NER 拡張 (nickname / 住所) | 予定 |

## 11. リリース要件 (SC-* 要約)

- **SC-1**: 日次セキュリティスキャン (pip-audit / osv / bandit)。72h SLA。
- **SC-3**: PyPI Trusted Publishing (OIDC)。リリース環境は手動承認。
- **SC-4**: Sigstore 署名 + SLSA provenance。
- **SC-5**: CycloneDX SBOM を Release 資産に添付。
- **SC-7**: 同梱マニフェストと `makkuro verify` による自己整合性確認。

## 12. 変更履歴

- 2026-04-19: 初版 (alpha 用スナップショット)。Phase 0〜7 の仕様を統合。
