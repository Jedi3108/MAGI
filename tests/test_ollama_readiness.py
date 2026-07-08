"""Tests for Ollama model-resolution helpers."""

import unittest

from magi.models.ollama import model_is_available, resolve_model_name


class TestOllamaReadiness(unittest.TestCase):
    def test_exact_model_resolution(self):
        available = ["llama3.2:latest", "mistral:latest"]

        self.assertEqual(
            resolve_model_name("llama3.2:latest", available),
            "llama3.2:latest",
        )

    def test_short_model_resolution_to_latest(self):
        available = ["llama3.2:latest", "mistral:latest"]

        self.assertEqual(
            resolve_model_name("llama3.2", available),
            "llama3.2:latest",
        )

    def test_prefix_model_resolution(self):
        available = ["qwen2.5:7b", "mistral:latest"]

        self.assertEqual(
            resolve_model_name("qwen2.5", available),
            "qwen2.5:7b",
        )

    def test_missing_model_resolution(self):
        available = ["mistral:latest"]

        self.assertIsNone(resolve_model_name("llama3.2", available))

    def test_model_is_available(self):
        available = ["gemma2:latest"]

        self.assertTrue(model_is_available("gemma2", available))
        self.assertFalse(model_is_available("llama3.2", available))


if __name__ == "__main__":
    unittest.main()
