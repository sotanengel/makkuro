"""Uvicorn runner for the proxy app.

Kept separate from ``app.py`` so tests can build the Starlette app without
starting a listening socket.
"""

from __future__ import annotations

import logging

import uvicorn

from makkuro.config import Config
from makkuro.proxy.app import build_app

logger = logging.getLogger("makkuro.server")


def run(config: Config) -> None:
    """Run the proxy in the current process until it's killed.

    Refuses non-loopback binds unless ``MAKKURO_ALLOW_PUBLIC_BIND=1``. The
    check is performed here (rather than in the Config loader) so ``build_app``
    remains usable in tests without the environment override.
    """
    import os

    if config.proxy.bind != "127.0.0.1" and os.environ.get("MAKKURO_ALLOW_PUBLIC_BIND") != "1":
        raise RuntimeError(
            "non-loopback bind requires MAKKURO_ALLOW_PUBLIC_BIND=1 to be set"
        )

    app = build_app(config)
    logger.info(
        "starting proxy on %s:%s (upstream hosts: %s)",
        config.proxy.bind,
        config.proxy.port,
        sorted(config.upstream_hosts),
    )
    uvicorn.run(
        app,
        host=config.proxy.bind,
        port=config.proxy.port,
        log_level="info",
        access_log=False,
        timeout_graceful_shutdown=config.proxy.shutdown_timeout_sec,
    )
