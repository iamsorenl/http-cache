# http-cache

Two functions: `cached_get` fetches a URL once, keeps the result on disk, and reads the file on every later call. `get_with_retry` is a plain GET that retries transient failures. Standard library only, Python 3.10+.

## Install

    pip install git+https://github.com/iamsorenl/http-cache

## Use

```python
from http_cache import cached_get

data = cached_get("https://pokeapi.co/api/v2/pokemon/pikachu", "cache/pikachu.json")
png = cached_get("https://example.com/a.png", "cache/a.png", kind="bytes")
```

`cached_get(url, cache_path, *, kind="json", sleep=0.2, timeout=30, ua=None, headers=None, refresh=False)`

- `kind` is `"json"`, `"text"` or `"bytes"`.
- The cache file is written to a temp file and renamed, so a crash never leaves half a file.
- A non-2xx response raises `urllib.error.HTTPError` and caches nothing.
- `sleep` is a polite pause after a real network request. Cache hits never sleep.
- `refresh=True` ignores the cached file and fetches again.

### get_with_retry

```python
from http_cache import get_with_retry

raw = get_with_retry("https://api.example.com/items", headers={"Authorization": "Bearer ..."})
```

`get_with_retry(url, *, retries=3, backoff=1.0, max_delay=8.0, timeout=30, headers=None)` returns the body as bytes.

- Retries 429, 5xx, timeouts and connection errors up to `retries` extra times.
- Waits `backoff * 2**attempt` seconds, or the server's `Retry-After` seconds, never more than `max_delay`.
- Any other 4xx raises `urllib.error.HTTPError` right away.

## Test

    python -m unittest discover -s tests

MIT licensed.
