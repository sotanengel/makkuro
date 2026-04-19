"""Configuration loader.

Resolves config from: built-in defaults -> user config (TOML) -> environment
variables -> CLI overrides. Phase 1 only handles the fields the proxy needs.
The complete schema (`docs/SPEC.md` §9) is enforced in Phase 3.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProviderConfig:
    upstream: str
    protocol: str = "anthropic"
    enabled: bool = True


@dataclass
class ProxyConfig:
    port: int = 8787
    bind: str = "127.0.0.1"
    request_timeout_sec: int = 120
    max_body_mb: int = 16


@dataclass
class RedactionConfig:
    mode: str = "mask"  # mask | block | warn
    rehydrate: bool = True


@dataclass
class SecurityConfig:
    network_allowlist_strict: bool = True
    integrity_check: bool = False  # enabled in Phase 2+ when release manifest exists


@dataclass
class Config:
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    redaction: RedactionConfig = field(default_factory=RedactionConfig)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    @property
    def upstream_hosts(self) -> frozenset[str]:
        out: set[str] = set()
        for p in self.providers.values():
            if not p.enabled:
                continue
            host = p.upstream.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
            if host:
                out.add(host.lower())
        return frozenset(out)


_DEFAULT_PROVIDERS: dict[str, ProviderConfig] = {
    "anthropic": ProviderConfig(
        upstream="https://api.anthropic.com",
        protocol="anthropic",
    ),
}


def default_config() -> Config:
    return Config(providers=dict(_DEFAULT_PROVIDERS))


def _apply_providers(cfg: Config, data: dict[str, Any]) -> None:
    for name, raw in data.items():
        if not isinstance(raw, dict):
            continue
        upstream = raw.get("upstream")
        if not isinstance(upstream, str):
            continue
        cfg.providers[name] = ProviderConfig(
            upstream=upstream,
            protocol=str(raw.get("protocol", name)),
            enabled=bool(raw.get("enabled", True)),
        )


def load_from_dict(data: dict[str, Any], base: Config | None = None) -> Config:
    cfg = base if base is not None else default_config()
    proxy = data.get("proxy") or {}
    if "port" in proxy:
        cfg.proxy.port = int(proxy["port"])
    if "bind" in proxy:
        cfg.proxy.bind = str(proxy["bind"])
    if "request_timeout_sec" in proxy:
        cfg.proxy.request_timeout_sec = int(proxy["request_timeout_sec"])
    if "max_body_mb" in proxy:
        cfg.proxy.max_body_mb = int(proxy["max_body_mb"])

    redaction = data.get("redaction") or {}
    if "mode" in redaction:
        mode = str(redaction["mode"])
        if mode not in ("mask", "block", "warn"):
            raise ValueError(f"invalid redaction.mode: {mode!r}")
        cfg.redaction.mode = mode
    if "rehydrate" in redaction:
        cfg.redaction.rehydrate = bool(redaction["rehydrate"])

    sec = data.get("security") or {}
    if "network_allowlist_strict" in sec:
        cfg.security.network_allowlist_strict = bool(sec["network_allowlist_strict"])
    if "integrity_check" in sec:
        cfg.security.integrity_check = bool(sec["integrity_check"])

    providers = data.get("providers")
    if isinstance(providers, dict):
        _apply_providers(cfg, providers)
    return cfg


def load_from_file(path: Path, base: Config | None = None) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return load_from_dict(raw, base=base)


def apply_env(cfg: Config, env: dict[str, str] | None = None) -> Config:
    env = env if env is not None else dict(os.environ)
    if (v := env.get("MAKKURO_PORT")):
        cfg.proxy.port = int(v)
    if (v := env.get("MAKKURO_BIND")):
        cfg.proxy.bind = v
    if (v := env.get("MAKKURO_NO_REHYDRATE")):
        cfg.redaction.rehydrate = v.lower() not in ("1", "true", "yes", "on")
    return cfg


def load(path: Path | None = None, env: dict[str, str] | None = None) -> Config:
    cfg = default_config()
    if path is not None and path.exists():
        cfg = load_from_file(path, base=cfg)
    return apply_env(cfg, env=env)
