#!/usr/bin/env python3
"""Client for the in-editor RLMesh demo control server.

Suite apps/gyms call :func:`ensure_demo` so Unreal loads the matching scenario
before ``RemoteEnv`` connects. The CLI remains for debugging::

  python integrations/unreal/demos/common/demo_client.py list
  python integrations/unreal/demos/common/demo_client.py status
  python integrations/unreal/demos/common/demo_client.py ensure chase_point
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE = "http://127.0.0.1:8878"

_CONTROL_HINT = (
    "Open the RLmeshSim Unreal editor (demo control starts automatically), "
    "or run in the Output Log:\n"
    '  py "G:/_UnrealProjects/RLmeshSim/Scripts/demo_control_server.py"'
)


class DemoControlError(RuntimeError):
    """Control server unreachable or returned an error."""


def request(
    method: str,
    path: str,
    *,
    base: str = DEFAULT_BASE,
    timeout: float = 130.0,
) -> dict[str, Any]:
    """HTTP JSON request to the demo control server. Raises DemoControlError."""
    url = f"{base.rstrip('/')}{path}"
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": body}
        payload["_http_status"] = exc.code
        if payload.get("ok") is False or exc.code >= 400:
            err = payload.get("error") or payload.get("status", {}).get("error") or body
            raise DemoControlError(f"demo control {method} {path} failed: {err}") from exc
        return payload
    except urllib.error.URLError as exc:
        raise DemoControlError(
            f"cannot reach demo control at {url}\n  {exc}\n{_CONTROL_HINT}"
        ) from exc


def get_status(*, base: str = DEFAULT_BASE) -> dict[str, Any]:
    return request("GET", "/v1/status", base=base, timeout=10.0)


def load_demo(demo_id: str, *, base: str = DEFAULT_BASE) -> dict[str, Any]:
    return request("POST", f"/v1/demos/{demo_id}/load", base=base)


def play(*, base: str = DEFAULT_BASE) -> dict[str, Any]:
    return request("POST", "/v1/play", base=base)


def stop(*, base: str = DEFAULT_BASE) -> dict[str, Any]:
    return request("POST", "/v1/stop", base=base)


def ensure_demo(
    demo_id: str,
    *,
    base: str = DEFAULT_BASE,
    wait_playing_sec: float = 30.0,
    poll_sec: float = 0.5,
) -> dict[str, Any]:
    """Load ``demo_id`` and begin Play if needed; return final status.

    No-op when status already has this ``demo_id`` and ``state == playing``.
    """
    demo_id = demo_id.strip()
    if not demo_id:
        raise ValueError("demo_id is required")

    status = get_status(base=base)
    if status.get("demo_id") == demo_id and status.get("state") == "playing":
        return status

    load_result = load_demo(demo_id, base=base)
    if load_result.get("ok") is False:
        raise DemoControlError(
            f"load {demo_id!r} failed: {load_result.get('error') or load_result}"
        )

    play_result = play(base=base)
    if play_result.get("ok") is False:
        raise DemoControlError(
            f"play after load {demo_id!r} failed: {play_result.get('error') or play_result}"
        )

    # PostPIEStarted reloads the control server and can reset /v1/status; the play
    # response is authoritative. Wait for EnvServer, then return.
    time.sleep(min(2.5, wait_playing_sec))
    last: dict[str, Any] = play_result.get("status") or {}
    try:
        polled = get_status(base=base)
        if polled.get("demo_id") == demo_id:
            last = polled
    except DemoControlError:
        pass
    if last.get("demo_id") != demo_id:
        last = {
            "server": "ok",
            "state": "playing",
            "demo_id": demo_id,
            "env_id": last.get("env_id"),
            "message": f"play requested for {demo_id}",
            "error": None,
        }
    return last


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=f"Control server base URL (default {DEFAULT_BASE})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health", help="GET /v1/health")
    sub.add_parser("list", help="GET /v1/demos")
    sub.add_parser("status", help="GET /v1/status")
    load_p = sub.add_parser("load", help="POST /v1/demos/<id>/load")
    load_p.add_argument("demo_id", help="reach_target | chase_point | …")
    sub.add_parser("play", help="POST /v1/play")
    sub.add_parser("stop", help="POST /v1/stop")
    ensure_p = sub.add_parser("ensure", help="load + play for demo_id if needed")
    ensure_p.add_argument("demo_id", help="reach_target | chase_point | …")

    args = parser.parse_args(argv)
    base = args.base.rstrip("/")

    try:
        if args.cmd == "health":
            data = request("GET", "/v1/health", base=base, timeout=10.0)
        elif args.cmd == "list":
            data = request("GET", "/v1/demos", base=base, timeout=10.0)
        elif args.cmd == "status":
            data = get_status(base=base)
        elif args.cmd == "load":
            data = load_demo(args.demo_id, base=base)
        elif args.cmd == "play":
            data = play(base=base)
        elif args.cmd == "stop":
            data = stop(base=base)
        elif args.cmd == "ensure":
            data = ensure_demo(args.demo_id, base=base)
        else:
            parser.error(f"unknown command {args.cmd}")
            return 2
    except DemoControlError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(data, indent=2))
    if data.get("ok") is False or data.get("_http_status", 200) >= 400:
        return 1
    if args.cmd == "load":
        status = data.get("status") or {}
        print(
            f"\nLoaded demo={status.get('demo_id')} env_id={status.get('env_id')}. "
            "Suite clients call ensure_demo automatically; or: demo_client.py play",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
