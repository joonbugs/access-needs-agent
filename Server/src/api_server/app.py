from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from aiohttp import web


def _project_root() -> Path:
    # api_server/ -> src/ -> Server/
    return Path(__file__).resolve().parent.parent.parent


def _events_path() -> Path:
    return _project_root() / "analysis" / "events.jsonl"


def _read_last_events(*, limit: int) -> list[dict[str, Any]]:
    path = _events_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for raw in lines[-limit:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
            if isinstance(item, dict):
                out.append(item)
        except Exception:
            continue
    return out


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return resp


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def analysis_latest(request: web.Request) -> web.Response:
    try:
        limit = int(request.query.get("limit", "50"))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 500))
    return web.json_response({"events": _read_last_events(limit=limit)})


def _sse_format(*, event: str | None, data: str) -> bytes:
    # SSE frame. data must not contain unescaped newlines across multiple "data:" lines.
    # We'll JSON-encode the payload so it's always a single line.
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {data}")
    lines.append("")  # blank line terminator
    return ("\n".join(lines) + "\n").encode("utf-8")


async def analysis_stream(request: web.Request) -> web.StreamResponse:
    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await resp.prepare(request)

    path = _events_path()
    last_size = path.stat().st_size if path.exists() else 0

    try:
        # Keep connection alive + stream new JSONL lines.
        while True:
            transport = request.transport
            if transport is None or transport.is_closing():
                break

            if path.exists():
                try:
                    current_size = path.stat().st_size
                except Exception:
                    current_size = last_size

                if current_size < last_size:
                    # File rotated/truncated
                    last_size = 0

                if current_size > last_size:
                    try:
                        with path.open("r", encoding="utf-8") as f:
                            f.seek(last_size)
                            chunk = f.read()
                        last_size = current_size
                        for raw in chunk.splitlines():
                            raw = raw.strip()
                            if not raw:
                                continue
                            try:
                                item = json.loads(raw)
                            except Exception:
                                continue
                            payload = json.dumps(item, ensure_ascii=False)
                            await resp.write(_sse_format(event="analysis", data=payload))
                    except Exception:
                        # If read fails, just continue; next loop may recover.
                        pass

            # Ping comment every few seconds so proxies don't kill us.
            await resp.write(b": ping\n\n")
            await asyncio.sleep(2.0)
    finally:
        try:
            await resp.write_eof()
        except Exception:
            pass

    return resp


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_route("GET", "/api/health", health)
    app.router.add_route("GET", "/api/analysis/latest", analysis_latest)
    app.router.add_route("GET", "/api/analysis/stream", analysis_stream)
    app.router.add_route("OPTIONS", "/{tail:.*}", lambda _req: web.Response(status=204))
    return app


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    web.run_app(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()

