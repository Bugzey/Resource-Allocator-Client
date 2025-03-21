"""
Tests for client
"""

import datetime as dt
from pathlib import Path
import tempfile
import unittest

from resource_allocator_client.client import (
    Cache,
    Client,
)


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache = Cache(
            server="test",
            email="test@example.com",
            path=Path(self.temp_dir.name) / "test.json",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init(self):
        self.assertIsNone(self.cache.token)
        self.assertEqual(self.cache.server, "test")
        self.assertEqual(self.cache.path.name, "test.json")

    def test_write(self):
        self.cache.token = "123"
        self.cache.expires_at = dt.datetime.now(tz=dt.timezone.utc)
        self.cache.write()

        file_path = Path(self.temp_dir.name) / "test.json"
        self.assertTrue(file_path.exists())
        with open(file_path) as cur_file:
            data = cur_file.read()

        self.assertIsNotNone(data)

    def test_read(self):
        self.cache.token = "123"
        self.cache.expires_at = dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(hours=5)
        self.cache.write()

        new_cache = Cache(server=self.cache.server, email=self.cache.email, path=self.cache.path)
        new_cache.read()
        self.assertEqual(new_cache.token, "123")
        self.assertIsNotNone(new_cache.expires_at)

    def test_replace_chars(self):
        self.assertEqual(
            Cache._replace_chars("http://127.0.0.1:5000/.json"),
            "http_127.0.0.1_5000_.json",
        )


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
