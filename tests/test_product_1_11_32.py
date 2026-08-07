#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.product import updater


class FakeResponse(object):
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def main():
    captured = {}
    original_urlopen = updater.urllib.request.urlopen
    original_time = updater.time.time

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["timeout"] = timeout
        return FakeResponse(b"1.11.32\n")

    updater.urllib.request.urlopen = fake_urlopen
    updater.time.time = lambda: 1234.567
    try:
        version = updater.remote_version()
    finally:
        updater.urllib.request.urlopen = original_urlopen
        updater.time.time = original_time

    assert version == "1.11.32", version
    assert captured["url"] == updater.REMOTE_VERSION_URL + "?cache_bust=1234567", captured["url"]
    assert captured["headers"].get("cache-control") == "no-cache", captured["headers"]
    assert captured["headers"].get("pragma") == "no-cache", captured["headers"]
    assert captured["timeout"] == 20, captured["timeout"]
    print("ALL 1.11.32 UPDATER CACHE-BUST TESTS PASSED")


if __name__ == "__main__":
    main()
