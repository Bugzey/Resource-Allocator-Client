"""
Unit tests for callback
"""
import threading
import unittest

import requests as req

from resource_allocator_client.callback import run_callback_server


class CallbackServerTestCase(unittest.TestCase):
    def test_callback_server(self):
        code_list = []
        thread = threading.Thread(
            target=run_callback_server,
            daemon=True,
            kwargs=dict(
                hostname="localhost",
                port=8080,
                variable=code_list,
            )
        )
        thread.start()
        response = req.get(url="http://localhost:8080", params={"code": "123"})
        thread.join(timeout=10)
        self.assertTrue(response.ok)
        self.assertEqual(code_list, ["123"])
