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
        self.assertEqual(str(self.cache.path), "test.json")

    def test_write(self):
        self.cache.token = "123"
        self.cache._paths[0] = Path(self.temp_dir.name)
        self.cache.write()

        file_path = Path(self.temp_dir.name) / "test.json"
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


class MakeParserTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = make_parser()
        self.base_args = ["-s", "test", "-e", "test@example.com"]

    def test_create(self):
        result = self.parser.parse_args([
            *self.base_args,
            "create", "resources", "name=bla", "top_resource_group_id=99",
            "invalid key=99%''\"====12", "quoted_text=\"there once was a time\"",
        ])
        self.assertEqual(result.action, "create")
        self.assertNotIn("id", dir(result))
        self.assertTrue(isinstance(result.data, list))
        self.assertTrue(isinstance(result.data[0], str))
        self.assertEquals(result.data[0], "name=bla")


class ParseDataArgsTestCase(unittest.TestCase):
    def test_parse_data_args(self):
        result = parse_data_args(["key=value", " other key = value ", "some key bla %'\"==invalid123"])
        self.assertEqual(result, {
            "key": "value",
            "other key": "value",
            "some key bla %'\"": "=invalid123",
        })

    def test_parse_data_args_no_equals(self):
        with self.assertRaises(ValueError):
            result = parse_data_args(["no equals"])
