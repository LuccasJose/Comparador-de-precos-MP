import os
import sys
import unittest

# Allow importing from ./src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gemini_client import (
    GeminiAuthError,
    GeminiParseError,
    GeminiResponseError,
    generate_menu_json,
    parse_gemini_json_response,
    sanitize_menu_payload,
    require_gemini_api_key,
)


class _Resp:
    def __init__(self, text):
        self.text = text


class _Model:
    def __init__(self, text):
        self._text = text

    def generate_content(self, prompt, **kwargs):
        return _Resp(self._text)


class TestGeminiClient(unittest.TestCase):
    def test_require_api_key_missing(self):
        with self.assertRaises(GeminiAuthError):
            require_gemini_api_key(env={})

    def test_parse_markdown_json(self):
        data, cleaned = parse_gemini_json_response("```json\n{\"x\": 1}\n```")
        self.assertEqual(data["x"], 1)
        self.assertEqual(cleaned, '{"x": 1}')

    def test_empty_response_raises(self):
        model = _Model("")
        with self.assertRaises(GeminiResponseError):
            generate_menu_json("prompt", model=model)

    def test_invalid_json_raises(self):
        model = _Model("nao e json")
        with self.assertRaises(GeminiParseError):
            generate_menu_json("prompt", model=model)

    def test_happy_path_with_mock_model(self):
        model = _Model("""```json\n{\"meu\": [{\"n\": \"a\", \"p\": 1.0}], \"conc\": []}\n```""")
        data, usage_stats = generate_menu_json("prompt", model=model)
        self.assertIn("meu", data)

    def test_sanitize_menu_payload_filters_invalid_names_and_parses_prices(self):
        raw = {
            "meu": [
                {"n": "82,00", "p": 82.0},
                {"n": "R$ 159,90", "p": "159,90"},
                {"n": "Pizza Calabresa", "p": "42,00"},
            ],
            "conc": [
                {"n": "Hamburguer Artesanal", "p": "242:98"},
                {"n": "123", "p": 10},
            ],
        }

        data = sanitize_menu_payload(raw)
        self.assertEqual(len(data["meu"]), 1)
        self.assertEqual(data["meu"][0]["n"], "Pizza Calabresa")
        self.assertEqual(data["meu"][0]["p"], 42.0)

        self.assertEqual(len(data["conc"]), 1)
        self.assertEqual(data["conc"][0]["n"], "Hamburguer Artesanal")
        self.assertEqual(data["conc"][0]["p"], 242.98)


if __name__ == "__main__":
    unittest.main()

