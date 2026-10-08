"""Availability probe for NFR-05 (search and Q&A availability over a defined pilot window).

Every ``--interval`` seconds, for ``--minutes`` minutes:
- search: ``POST /search`` with a fixed query must return HTTP 200 (a real request through the
  stack);
- qa: ``GET /ready`` must report "ready" with every check ok (database, embedding model, Ollama).
  This is a dependency proxy for Q&A; it does not generate answers (they would fill the history).

Each probe is appended to a JSON-lines log; ``--summarize LOG`` prints availability for a log.
Standard library only, so it runs with any Python 3.12+.

    python scripts/uptime_probe.py --minutes 60 --out eval/uptime/x.jsonl
    python scripts/uptime_probe.py --summarize eval/uptime/x.jsonl
"""

import argparse
import itertools
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SEARCH_BODY = json.dumps({"query": "attention mechanism", "top_k": 3}).encode()


def _call(
    url: str, body: bytes | None, timeout: float
) -> tuple[int | None, Any, float, str | None]:
    request = urllib.request.Request(  # noqa: S310 - URL comes from the operator's --base-url
        url, data=body, headers={"Content-Type": "application/json"} if body else {}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read() or b"null")
            return response.status, payload, (time.perf_counter() - started) * 1000, None
    except urllib.error.HTTPError as exc:
        return exc.code, None, (time.perf_counter() - started) * 1000, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return None, None, (time.perf_counter() - started) * 1000, type(exc).__name__


def probe(base_url: str, timeout: float) -> dict[str, Any]:
    status, _, search_ms, search_err = _call(f"{base_url}/search", SEARCH_BODY, timeout)
    ready_status, ready, ready_ms, ready_err = _call(f"{base_url}/ready", None, timeout)
    checks = (ready or {}).get("checks", {}) if isinstance(ready, dict) else {}
    qa_ok = (
        ready_status == 200
        and isinstance(ready, dict)
        and ready.get("status") == "ready"
        and bool(checks)
        and all(c.get("ok") for c in checks.values())
    )
    return {
        "ts": datetime.now(UTC).isoformat(),
        "search_ok": status == 200,
        "search_ms": round(search_ms, 1),
        "search_error": search_err,
        "qa_ok": qa_ok,
        "ready_ms": round(ready_ms, 1),
        "ready_error": ready_err or (None if qa_ok else "not ready"),
        "failed_checks": sorted(k for k, c in checks.items() if not c.get("ok")),
    }


def summarize(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise SystemExit("empty log")
    n = len(rows)
    stamps = [datetime.fromisoformat(r["ts"]) for r in rows]
    gaps = [(b - a).total_seconds() for a, b in itertools.pairwise(stamps)]
    median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
    return {
        "log": path.as_posix(),
        "window_start": rows[0]["ts"],
        "window_end": rows[-1]["ts"],
        "probes": n,
        "search_availability": round(sum(r["search_ok"] for r in rows) / n, 4),
        "qa_availability": round(sum(r["qa_ok"] for r in rows) / n, 4),
        "search_failures": [r["ts"] for r in rows if not r["search_ok"]],
        "qa_failures": [r["ts"] for r in rows if not r["qa_ok"]],
        # Gaps longer than 2x the median spacing mean the probe itself was not running (e.g. sleep);
        # such periods are unobserved, not counted as up or down.
        "unobserved_gaps_s": [round(g) for g in gaps if g > 2 * median_gap],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8080/api/v1")
    parser.add_argument("--minutes", type=float, default=60)
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summarize", type=Path, help="print availability for an existing log")
    args = parser.parse_args()

    if args.summarize:
        print(json.dumps(summarize(args.summarize), indent=2))
        return
    if args.out is None:
        parser.error("--out is required when probing")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.minutes * 60
    with args.out.open("a", encoding="utf-8", newline="\n") as log:
        while time.monotonic() < deadline:
            started = time.monotonic()
            log.write(json.dumps(probe(args.base_url.rstrip("/"), args.timeout)) + "\n")
            log.flush()
            time.sleep(max(0.0, args.interval - (time.monotonic() - started)))
    print(json.dumps(summarize(args.out), indent=2))


if __name__ == "__main__":
    main()
