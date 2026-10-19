"""Fleet app discovery for the webapp Apps Hub page.

Curated registry (ports match mcp-central-docs/operations/WEBAPP_PORTS.md)
plus operator extension via FLEET_EXTRA_PORTS="name:port,name:port".
Every entry is live-probed on each call -- status is observed, never assumed.
Reachable-but-unlisted apps land in "experimental", per WEBAPP_SOTA_STANDARDS.
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fleet", tags=["fleet"])

REGISTRY: list[dict] = [
    {
        "name": "leanforge-mcp",
        "label": "Leanforge (this app)",
        "backend_port": 10867,
        "frontend_port": 10868,
        "health_path": "/api/health",
    },
    {
        "name": "starts-launcher",
        "label": "Fleet Starts Launcher",
        "backend_port": 10791,
        "frontend_port": 10791,
        "health_path": "/api/health",
    },
]


def _extra_apps() -> list[dict]:
    apps = []
    for item in os.environ.get("FLEET_EXTRA_PORTS", "").split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        name, port = item.split(":", 1)
        try:
            apps.append(
                {
                    "name": name.strip(),
                    "label": name.strip(),
                    "backend_port": int(port.strip()),
                    "frontend_port": int(port.strip()),
                    "health_path": "/api/health",
                }
            )
        except ValueError:
            logger.warning("Ignoring malformed FLEET_EXTRA_PORTS entry: %r", item)
    return apps


async def _probe(base: str, health_path: str, timeout: float = 1.5) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base}{health_path}")
            if resp.status_code == 404:
                resp = await client.get(f"{base}/")
            if resp.status_code < 500:
                version = None
                try:
                    version = resp.json().get("version")
                except (ValueError, AttributeError):
                    version = None
                return {"online": True, "http_status": resp.status_code, "version": version}
    except httpx.HTTPError as exc:
        logger.debug("Fleet probe %s%s failed: %s", base, health_path, exc)
    return {"online": False, "http_status": None, "version": None}


@router.get("/apps")
async def fleet_apps():
    """Return registered apps with live status plus experimental (unlisted) hits."""
    registered = []
    for app in REGISTRY:
        base = f"http://127.0.0.1:{app['backend_port']}"
        probe = await _probe(base, app["health_path"])
        registered.append(
            {
                **app,
                "url": f"http://127.0.0.1:{app['frontend_port']}",
                **probe,
            }
        )
    experimental = []
    for app in _extra_apps():
        if any(r["backend_port"] == app["backend_port"] for r in registered):
            continue
        base = f"http://127.0.0.1:{app['backend_port']}"
        probe = await _probe(base, app["health_path"])
        experimental.append({**app, "url": base, **probe})
    return {"registered": registered, "experimental": experimental}
