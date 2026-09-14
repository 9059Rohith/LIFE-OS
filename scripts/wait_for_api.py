"""Wait for an HTTP readiness response, with a bounded deadline."""

import argparse
import time
from http.client import HTTPException
from urllib.error import URLError
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8010/ready")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(args.url, timeout=min(2, max(0.1, deadline - time.monotonic()))) as response:
                if response.status == 200:
                    print("API is ready")
                    return
        except (URLError, OSError, HTTPException):
            pass
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    raise SystemExit("API readiness deadline exceeded")


if __name__ == "__main__":
    main()
