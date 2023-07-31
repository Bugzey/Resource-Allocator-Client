"""
Tests for client
"""

from pathlib import Path
import tempfile
import unittest

from resource_allocator_client.client import (
    Cache,
    Client,
)


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


class ClientTestCase(unittest.TestCase):
    def setUp(self):
        self.client = Client(
            server="server////",
            email="email@example.com",
            password="some_password",
        )

    def test_init(self):
        self.assertIsInstance(self.client, Client)
        self.assertEqual(self.client.server, "https://server")
        self.assertFalse(self.client.azure_login)

        #   No password
        with self.assertRaises(ValueError):
            _ = Client(server="server", email="email@example.com")

        #   Azure and password given
        with self.assertRaises(ValueError):
            _ = Client(
                server="server",
                email="email@example.com",
                password="password",
                azure_login=True,
            )
