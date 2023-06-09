"""
Unit tests for the main module
"""

import unittest
import tempfile
import threading

from resource_allocator_client.main import *


class CallbackServerTestCase(unittest.TestCase):
    def test_callback_server(self):
        code_list = []
        thread = threading.Thread(
            target=run_callback_server,
            kwargs={"code_list": code_list},
            daemon=True,
        )
        thread.start()
        response = req.get(url="http://localhost:8080", params={"code": "123"})
        thread.join(timeout=10)
        self.assertTrue(response.ok)
        self.assertEqual(code_list, ["123"])


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.cache = Cache(server="test")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init(self):
        self.assertIsNone(self.cache.token)
        self.assertEqual(self.cache.server, "test")
        self.assertEqual(str(self.cache.path), "test")

    def test_write(self):
        self.cache.token = "123"
        self.cache._paths[0] = Path(self.temp_dir.name)
        self.cache.write()

        file_path = Path(self.temp_dir.name) / "test"
        self.assertTrue(file_path.exists())
        with open(file_path) as cur_file:
            data = cur_file.read()

        self.assertIsNotNone(data)

    def test_read(self):
        self.cache.token = "123"
        self.cache._paths[0] = Path(self.temp_dir.name)
        self.cache.write()

        result = self.cache.read()
        self.assertEqual(result, {"server": self.cache.server, "token": "123"})
        self.assertEqual(self.cache.token, "123")
