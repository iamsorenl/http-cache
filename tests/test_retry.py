import http.server
import threading
import unittest
import urllib.error
from unittest import mock

from http_cache import get_with_retry


class Handler(http.server.BaseHTTPRequestHandler):
    script = []  # (status, headers) per request; last entry repeats
    hits = 0

    def do_GET(self):
        i = min(Handler.hits, len(Handler.script) - 1)
        Handler.hits += 1
        status, headers = Handler.script[i]
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if status == 200:
            self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


class RetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}/x"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def run_script(self, script, **kw):
        Handler.script, Handler.hits = script, 0
        with mock.patch("http_cache.time.sleep") as sleep:
            try:
                return get_with_retry(self.url, **kw), sleep
            except urllib.error.HTTPError as e:
                return e, sleep

    def test_retries_5xx_then_succeeds_with_backoff(self):
        body, sleep = self.run_script([(503, {}), (500, {}), (200, {})])
        self.assertEqual(body, b"ok")
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.0, 2.0])

    def test_honors_retry_after_on_429_capped(self):
        body, sleep = self.run_script([(429, {"Retry-After": "3"}), (429, {"Retry-After": "60"}), (200, {})])
        self.assertEqual(body, b"ok")
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [3.0, 8.0])

    def test_4xx_raises_without_retry(self):
        err, sleep = self.run_script([(404, {})])
        self.assertEqual(err.code, 404)
        self.assertEqual(Handler.hits, 1)
        sleep.assert_not_called()

    def test_gives_up_after_retries(self):
        err, sleep = self.run_script([(502, {})], retries=2)
        self.assertEqual(err.code, 502)
        self.assertEqual(Handler.hits, 3)

    def test_connection_error_retries_then_raises(self):
        with mock.patch("http_cache.time.sleep") as sleep:
            with self.assertRaises(urllib.error.URLError):
                get_with_retry("http://127.0.0.1:1/", retries=1)
        self.assertEqual(sleep.call_count, 1)


if __name__ == "__main__":
    unittest.main()
