from __future__ import annotations

from pathlib import Path

import pytest

from makkuro.config import apply_env, default_config, load, load_from_dict


def test_default_config_has_all_providers():
    cfg = default_config()
    assert {"anthropic", "openai", "gemini"} <= set(cfg.providers)
    assert "api.anthropic.com" in cfg.upstream_hosts
    assert "api.openai.com" in cfg.upstream_hosts
    assert "generativelanguage.googleapis.com" in cfg.upstream_hosts


def test_load_from_dict_override():
    cfg = load_from_dict(
        {
            "proxy": {"port": 9999, "bind": "127.0.0.1"},
            "redaction": {"mode": "warn", "rehydrate": False},
            "providers": {
                "openai": {
                    "upstream": "https://api.openai.com",
                    "protocol": "openai",
                    "enabled": True,
                }
            },
        }
    )
    assert cfg.proxy.port == 9999
    assert cfg.redaction.mode == "warn"
    assert cfg.redaction.rehydrate is False
    assert "openai" in cfg.providers
    assert "api.openai.com" in cfg.upstream_hosts


def test_load_from_dict_invalid_mode():
    with pytest.raises(ValueError):
        load_from_dict({"redaction": {"mode": "nonsense"}})


def test_apply_env_overrides(tmp_path: Path):
    cfg = default_config()
    apply_env(cfg, env={"MAKKURO_PORT": "1234", "MAKKURO_NO_REHYDRATE": "1"})
    assert cfg.proxy.port == 1234
    assert cfg.redaction.rehydrate is False


def test_load_with_toml_file(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text(
        """\
[proxy]
port = 7000

[redaction]
mode = "block"
""",
        encoding="utf-8",
    )
    cfg = load(p)
    assert cfg.proxy.port == 7000
    assert cfg.redaction.mode == "block"
