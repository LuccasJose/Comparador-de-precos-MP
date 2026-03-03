import os
import sys
import unittest

# Allow importing from ./src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import utils


class TestLimparJsonResposta(unittest.TestCase):
    def test_removes_markdown_fences(self):
        raw = """```json\n{\"a\": 1}\n```"""
        self.assertEqual(utils.limpar_json_resposta(raw), '{"a": 1}')

    def test_extracts_json_with_extra_text(self):
        raw = "Aqui esta o resultado:\n```json\n{\"meu\": [], \"conc\": []}\n```\nObrigado!"
        self.assertEqual(utils.limpar_json_resposta(raw), '{"meu": [], "conc": []}')

    def test_none_returns_empty(self):
        self.assertEqual(utils.limpar_json_resposta(None), "")


if __name__ == "__main__":
    unittest.main()

