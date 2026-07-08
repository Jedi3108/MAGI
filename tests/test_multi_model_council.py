"""Tests for multi-model council assignment."""

import unittest
from unittest.mock import patch

from magi.protocol.engine import MagiEngine


class TestMultiModelCouncil(unittest.TestCase):
    def test_uses_preferred_models_when_available(self):
        available = [
            "qwen2.5:latest",
            "gemma2:latest",
            "mistral:latest",
            "llama3.1:latest",
            "llama3.2:latest",
        ]

        with patch("magi.protocol.engine.installed_models", return_value=available):
            engine = MagiEngine(mock=False)

        self.assertEqual(engine.models["MELCHIOR"], "qwen2.5:latest")
        self.assertEqual(engine.models["BALTHASAR"], "gemma2:latest")
        self.assertEqual(engine.models["CASPER"], "mistral:latest")
        self.assertEqual(engine.models["ARTABAN"], "llama3.1:latest")
        self.assertEqual(engine.chair_model, "llama3.2:latest")
        self.assertEqual(engine.model_notes, [])

    def test_falls_back_to_default_model_when_preferred_missing(self):
        available = ["llama3.2:latest"]

        with patch("magi.protocol.engine.installed_models", return_value=available):
            engine = MagiEngine(mock=False)

        self.assertEqual(engine.models["MELCHIOR"], "llama3.2:latest")
        self.assertEqual(engine.models["BALTHASAR"], "llama3.2:latest")
        self.assertEqual(engine.models["CASPER"], "llama3.2:latest")
        self.assertEqual(engine.models["ARTABAN"], "llama3.2:latest")

        self.assertTrue(any("MELCHIOR fallback" in note for note in engine.model_notes))
        self.assertTrue(any("BALTHASAR fallback" in note for note in engine.model_notes))
        self.assertTrue(any("CASPER fallback" in note for note in engine.model_notes))
        self.assertTrue(any("ARTABAN fallback" in note for note in engine.model_notes))

    def test_forced_model_overrides_preferred_models(self):
        available = [
            "qwen2.5:latest",
            "gemma2:latest",
            "mistral:latest",
            "llama3.1:latest",
            "llama3.2:latest",
        ]

        with patch("magi.protocol.engine.installed_models", return_value=available):
            engine = MagiEngine(model="llama3.2", mock=False)

        self.assertEqual(engine.models["MELCHIOR"], "llama3.2:latest")
        self.assertEqual(engine.models["BALTHASAR"], "llama3.2:latest")
        self.assertEqual(engine.models["CASPER"], "llama3.2:latest")
        self.assertEqual(engine.models["ARTABAN"], "llama3.2:latest")
        self.assertEqual(engine.chair_model, "llama3.2:latest")

    def test_same_flag_uses_default_model_for_all_members(self):
        available = [
            "qwen2.5:latest",
            "gemma2:latest",
            "mistral:latest",
            "llama3.1:latest",
            "llama3.2:latest",
        ]

        with patch("magi.protocol.engine.installed_models", return_value=available):
            engine = MagiEngine(mock=False, same=True)

        self.assertEqual(engine.models["MELCHIOR"], "llama3.2:latest")
        self.assertEqual(engine.models["BALTHASAR"], "llama3.2:latest")
        self.assertEqual(engine.models["CASPER"], "llama3.2:latest")
        self.assertEqual(engine.models["ARTABAN"], "llama3.2:latest")


if __name__ == "__main__":
    unittest.main()
