# http-cache

One function: fetch a URL once, keep the result on disk, and read the file on every later call. Standard library only, Python 3.10+.

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

## Test

    python -m unittest discover -s tests

MIT licensed.
