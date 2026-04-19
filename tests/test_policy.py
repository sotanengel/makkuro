from __future__ import annotations

from makkuro.policy import load_schema, validate


def test_schema_loads():
    schema = load_schema()
    assert schema["title"] == "makkuro configuration"


def test_valid_config_passes():
    data = {
        "schema_version": 1,
        "proxy": {"port": 8787, "bind": "127.0.0.1"},
        "redaction": {"mode": "mask", "rehydrate": True},
        "providers": {
            "anthropic": {
                "upstream": "https://api.anthropic.com",
                "protocol": "anthropic",
                "enabled": True,
            }
        },
    }
    report = validate(data)
    assert report.ok, report.errors


def test_invalid_mode_is_rejected():
    report = validate({"redaction": {"mode": "nonsense"}})
    assert not report.ok
    assert any("enum" in e.message for e in report.errors)


def test_unknown_top_level_property_is_rejected():
    report = validate({"nonsense_key": 1})
    assert not report.ok


def test_port_out_of_range_is_rejected():
    report = validate({"proxy": {"port": 80}})
    assert not report.ok
    assert any("minimum" in e.message for e in report.errors)


def test_non_https_upstream_is_rejected():
    report = validate(
        {
            "providers": {
                "anthropic": {
                    "upstream": "http://api.anthropic.com",
                    "protocol": "anthropic",
                }
            }
        }
    )
    assert not report.ok
    assert any("pattern" in e.message for e in report.errors)
