"""
Unit tests for the main module
"""

import unittest

from resource_allocator_client.main import (
    Parser,
)


class MakeParserTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = Parser().make_parser()
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
        self.assertEqual(result.data[0], "name=bla")


class ParseDataArgsTestCase(unittest.TestCase):
    def test_parse_data_args(self):
        result = Parser.parse_data_args([
            "key=value",
            " other key = value ",
        ])
        self.assertEqual(
            result, {
                "key": "value",
                "other key": "value",
            },
        )

    def test_parse_data_args_special(self):
        result = Parser.parse_data_args([
            "bool_yes=yes",
            "bool_no=no",
            "bool_true=true",
            "bool_false =false",
            "int =123",
            "dict=bla=true,other=bla",
        ])
        self.assertEqual(
            result,
            {
                "bool_yes": True,
                "bool_no": False,
                "bool_true": True,
                "bool_false" : False,
                "int": 123,
                "dict": {
                    "bla": True,
                    "other": "bla",
                },
            },
        )

    def test_parse_data_args_no_equals(self):
        with self.assertRaises(ValueError):
            _ = Parser.parse_data_args(["no equals"])
