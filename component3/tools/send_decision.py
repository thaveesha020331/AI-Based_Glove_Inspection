"""Send a sorting decision to Component 3 and optionally wait for completion."""

import argparse
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url: str, payload: dict[str, str] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"device returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"cannot reach Component 3: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="for example http://192.168.1.120")
    parser.add_argument("event_id", help="unique glove correlation ID")
    parser.add_argument(
        "decision",
        choices=("ACCEPT", "DEFECTIVE", "WRONG_ORIENTATION"),
    )
    parser.add_argument("--wait", action="store_true", help="poll until terminal state")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    accepted = request_json(
        f"{base_url}/decision",
        {"event_id": args.event_id, "decision": args.decision},
    )
    print(json.dumps(accepted, indent=2))

    if not args.wait:
        return 0

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        status = request_json(f"{base_url}/status")
        print(json.dumps(status, indent=2))
        if status.get("state") in {"COMPLETE", "ERROR"}:
            return 0 if status["state"] == "COMPLETE" else 2
        time.sleep(0.25)

    print("Timed out waiting for a terminal sorter state")
    return 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(error)
        raise SystemExit(1) from error

