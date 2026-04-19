# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- First-class `brew` install path. `Formula/makkuro.rb` ships in-repo
  using `Language::Python::Virtualenv`; consumers do
  `brew tap sotanengel/makkuro https://github.com/sotanengel/makkuro.git`
  then `brew install makkuro` (or `--HEAD` before the first tag).
- `scripts/update_formula.py` regenerates PyPI resource blocks
  (`--check` gate wired into CI so the Formula can't drift).
- `examples/makkuro.toml` — a commented template for user configs;
  validated by `makkuro policy validate`.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue / PR templates.
- README lead section rewritten for non-engineers (benefit-first,
  30-second before/after example, 3-command quickstart).
- Schema now formally accepts `redaction.custom_patterns` and
  `redaction.allow_list` (the runtime already honored them).

### Changed
- Version bumped to **0.1.0** and classifier switched from
  *Pre-Alpha* to *Alpha*.
- `starlette` 0.41.3 → **0.49.1** to patch `GHSA-2c2j-9gv5-cj73` and
  `GHSA-7f5h-v6xp-fcq8`. `pytest` 8.3.4 → **9.0.3** to patch
  `GHSA-6w46-j5rx-g56g`.
- `security.yml` audit / osv jobs reworked so they actually scan the
  runtime dependency closure without requiring makkuro to exist on
  PyPI first.

## [0.0.1] — Phase 0 through Phase 7

Pre-release iteration. Tracked by phase; summaries below.

### Phase 7 — Age-encrypted persistent vault (#16)
- Optional `pyrage` backend for placeholder ↔ value maps that
  survive proxy restarts.
- `[vault]` TOML section with `purge_after_days` and
  `rotate_reminder_days`.

### Phase 6 — Release pipeline + self-integrity verification (#15)
- PyPI Trusted Publishing (OIDC) workflow.
- Sigstore signing + SLSA L3 build provenance.
- CycloneDX SBOM generation.
- `makkuro verify` — hash-check installed files against a bundled
  release manifest.

### Phase 5 — SSE streaming with look-back rehydration (#14)
- Redaction and rehydration across SSE chunk boundaries so
  streaming responses stay consistent with non-streaming.

### Phase 4 — Config / redactor / app wiring for custom patterns + allow-list (#6, #13)
- User-defined regex patterns (`redaction.custom_patterns`).
- Allow-list to exempt known-safe literals
  (`redaction.allow_list`).
- Security CI (pip-audit, osv-scanner, bandit).

### Phase 3 — MCP deep-redact + gitleaks-style secret detectors (#5)
- Walks MCP `tool_use` / `tool_result` payloads.
- Adds gitleaks-inspired detectors for common API keys and tokens.

### Phase 2 — OpenAI + Gemini adapters, audit log, schema validator (#4)
- Protocol adapters for OpenAI and Google Gemini alongside the
  existing Anthropic adapter.
- JSONL audit log (metadata only; never the raw value).
- `makkuro policy validate` against the bundled JSON schema.

### Phase 1 — Runtime wiring, CLI `start`, proxy tests (#3)
- Starlette-based ASGI proxy with upstream allow-list.
- Config loader (defaults → TOML → env → CLI).
- In-memory placeholder vault and Anthropic protocol adapter.

### Phase 0 — Scaffolding + baseline detectors + toy benchmark (#1)
- Project layout, `ruff`, pytest.
- Baseline detectors: EMAIL, JP_MOBILE, JP_LANDLINE, JP_ZIP,
  JP_CREDIT_CARD (Luhn), JP_MYNUMBER (checksum).
- Toy benchmark harness reporting per-type and macro F1.

[Unreleased]: https://github.com/sotanengel/makkuro/compare/v0.0.1...HEAD
