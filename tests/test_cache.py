import http.server
import os
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

import http_cache
from http_cache import cached_get


class Handler(http.server.BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        Handler.hits.append((self.path, self.headers.get("User-Agent"), self.headers.get("X-Test")))
        if self.path == "/missing":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/missing")
            self.end_headers()
            return
        body = {"/j": b'{"a": 1}', "/t": "héllo".encode(), "/b": b"\x00\xff"}.get(self.path, b"{}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class CacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        Handler.hits.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "sub", "f")
        patcher = mock.patch.object(http_cache.time, "sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_miss_fetches_and_writes(self):
        self.assertEqual(cached_get(self.base + "/j", self.path), {"a": 1})
        self.assertEqual(len(Handler.hits), 1)
        with open(self.path) as f:
            self.assertEqual(f.read(), '{"a": 1}')
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["f"])  # no tmp left

    def test_hit_makes_no_request(self):
        cached_get(self.base + "/j", self.path)
        Handler.hits.clear()
        self.assertEqual(cached_get(self.base + "/j", self.path), {"a": 1})
        self.assertEqual(Handler.hits, [])

    def test_kinds(self):
        self.assertEqual(cached_get(self.base + "/b", self.path, kind="bytes"), b"\x00\xff")
        p2 = self.path + "2"
        self.assertEqual(cached_get(self.base + "/t", p2, kind="text"), "héllo")
        self.assertEqual(cached_get(self.base + "/t", p2, kind="text"), "héllo")  # hit
        self.assertEqual(cached_get(self.base + "/b", self.path, kind="bytes"), b"\x00\xff")
        with self.assertRaises(ValueError):
            cached_get(self.base + "/j", self.path + "3", kind="xml")

    def test_non_2xx_raises_and_writes_nothing(self):
        for url in ("/missing", "/redirect"):
            with self.assertRaises(urllib.error.HTTPError):
                cached_get(self.base + url, self.path)
        self.assertFalse(os.path.exists(self.path))
        self.assertFalse(os.path.exists(os.path.dirname(self.path)) and os.listdir(os.path.dirname(self.path)))
        self.sleep.assert_not_called()

    def test_bad_json_writes_nothing(self):
        with self.assertRaises(ValueError):
            cached_get(self.base + "/t", self.path)  # not JSON
        self.assertFalse(os.path.exists(self.path))

    def test_refresh_refetches(self):
        cached_get(self.base + "/j", self.path)
        cached_get(self.base + "/j", self.path, refresh=True)
        self.assertEqual(len(Handler.hits), 2)

    def test_sleep_only_on_network_hits(self):
        cached_get(self.base + "/j", self.path, sleep=0.7)
        self.sleep.assert_called_once_with(0.7)
        cached_get(self.base + "/j", self.path, sleep=0.7)
        self.assertEqual(self.sleep.call_count, 1)
        cached_get(self.base + "/j", self.path, sleep=0)
        cached_get(self.base + "/j", self.path, sleep=0, refresh=True)
        self.assertEqual(self.sleep.call_count, 1)

    def test_ua_and_headers(self):
        cached_get(self.base + "/j", self.path, ua="me/1", headers={"X-Test": "y"})
        self.assertEqual(Handler.hits[0][1:], ("me/1", "y"))


if __name__ == "__main__":
    unittest.main()
