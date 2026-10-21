#!/usr/bin/env python3

import ipaddress
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

TARGET_ASNS = [
    "AS8075",
    "AS12222",
    "AS16702",
    "AS20940",
    "AS21342",
    "AS35994",
    "AS18717",
    "AS32787",
    "AS16509",
    "AS14618",
    "AS36263",
    "AS13335",
    "AS395747",
    "AS209242",
    "AS14061",
    "AS133165",
    "AS54113",
    "AS15169",
    "AS32934",
    "AS29405",
    "AS60068",
    "AS62041",
    "AS211157",
    "AS44893",
    "AS16276",
    "AS199524",
    "AS21859",
    "AS46652",
    "AS48326",
    "AS21276",
    "AS36459",
]

API_URL = "https://stat.ripe.net/data/announced-prefixes/data.json?resource={asn}"
TIMEOUT = int(os.environ.get("PREFIXES_TIMEOUT", "30"))
MAX_WORKERS = int(os.environ.get("PREFIXES_MAX_WORKERS", "4"))
RETRIES = int(os.environ.get("PREFIXES_RETRIES", "3"))
ALLOW_PARTIAL = os.environ.get("PREFIXES_ALLOW_PARTIAL", "0") == "1"


def fetch_prefixes(asn):
    last_error = None
    for attempt in range(RETRIES):
        request = urllib.request.Request(
            API_URL.format(asn=asn),
            headers={"User-Agent": "smartgate-prefixes/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = json.load(response)
            prefixes = []
            for item in payload.get("data", {}).get("prefixes", []):
                prefix = item.get("prefix")
                if prefix and ":" not in prefix:
                    prefixes.append(prefix)
            return prefixes
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            last_error = exc
        except Exception as exc:
            last_error = exc
        time.sleep(attempt + 1)
    raise last_error


def sort_key(prefix):
    network = ipaddress.ip_network(prefix, strict=False)
    return int(network.network_address), network.prefixlen


def main():
    prefixes = set()
    errors = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_prefixes, asn): asn for asn in TARGET_ASNS}
        for future in as_completed(futures):
            asn = futures[future]
            try:
                prefixes.update(future.result())
            except Exception as exc:
                errors.append((asn, exc))

    for asn, exc in errors:
        print(f"[ERROR] {asn}: {exc}", file=sys.stderr)

    if errors:
        print(f"[ERROR] Failed to fetch {len(errors)} ASN(s)", file=sys.stderr)
        if not ALLOW_PARTIAL:
            return 1

    if not prefixes:
        print("[ERROR] No prefixes downloaded", file=sys.stderr)
        return 1

    for prefix in sorted(prefixes, key=sort_key):
        print(prefix)

    print(
        f"[INFO] Collected {len(prefixes)} prefixes from {len(TARGET_ASNS)} ASNs",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
