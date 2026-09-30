"""Disk-cached HTTP GET, stdlib only."""
import json
import os
import tempfile
import time
import urllib.error
import urllib.request

__all__ = ["cached_get"]


def _decode(raw, kind):
    if kind == "bytes":
        return raw
    if kind == "text":
        return raw.decode("utf-8")
    if kind == "json":
        return json.loads(raw)
    raise ValueError(f"kind must be 'json', 'bytes' or 'text', got {kind!r}")


def cached_get(url, cache_path, *, kind="json", sleep=0.2, timeout=30,
               ua=None, headers=None, refresh=False):
    """GET url and cache it at cache_path; later calls read the file.

    kind: "json" (parsed, cached as compact JSON), "text" (utf-8 str) or
    "bytes". Non-2xx responses raise (urllib.error.HTTPError) and cache
    nothing. sleep seconds are waited after a network fetch, never on a hit.
    refresh=True ignores an existing cache file and refetches.
    """
    if kind not in ("json", "bytes", "text"):
        raise ValueError(f"kind must be 'json', 'bytes' or 'text', got {kind!r}")
    cache_path = os.fspath(cache_path)
    if not refresh and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return _decode(f.read(), kind)

    hdrs = dict(headers or {})
    if ua:
        hdrs["User-Agent"] = ua
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if not 200 <= resp.status < 300:
            raise urllib.error.HTTPError(url, resp.status, "non-2xx", resp.headers, None)
        raw = resp.read()

    data = _decode(raw, kind)  # bad JSON/UTF-8 raises before anything is written
    to_write = json.dumps(data).encode() if kind == "json" else raw

    d = os.path.dirname(cache_path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(to_write)
        os.replace(tmp, cache_path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    if sleep:
        time.sleep(sleep)
    return data
