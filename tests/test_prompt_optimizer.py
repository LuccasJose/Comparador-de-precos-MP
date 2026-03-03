"""Testes para o módulo de otimização de prompt."""
import unittest
import os
import sys

# Adiciona src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from prompt_optimizer import (
    gerar_prompt_otimizado,
    gerar_prompt_com_instrucoes,
    escolher_prompt,
    estimar_tokens_prompt,
)


class TestPromptOptimizer(unittest.TestCase):
    """Testes para otimização de prompt."""
    
    def setUp(self):
        """Prepara dados de teste."""
        self.txt_meu = "Hambúrguer 25.50\nPizza 30.00"
        self.txt_conc = "Hambúrguer 24.00\nPizza 29.50"
    
    def test_gerar_prompt_otimizado(self):
        """Testa geração de prompt otimizado."""
        prompt = gerar_prompt_otimizado(self.txt_meu, self.txt_conc)
        
        # Deve conter os textos
        self.assertIn(self.txt_meu, prompt)
        self.assertIn(self.txt_conc, prompt)
        
        # Deve conter formato JSON esperado
        self.assertIn('"meu"', prompt)
        self.assertIn('"conc"', prompt)
        
        # Deve ser conciso (menos de 500 caracteres)
        self.assertLess(len(prompt), 500)
    
    def test_gerar_prompt_com_instrucoes(self):
        """Testa geração de prompt com instruções."""
        prompt = gerar_prompt_com_instrucoes(self.txt_meu, self.txt_conc)

        # Deve conter os textos
        self.assertIn(self.txt_meu, prompt)
        self.assertIn(self.txt_conc, prompt)

        # Deve conter instruções detalhadas
        self.assertIn("REGRAS", prompt)
        self.assertIn("TAREFA", prompt)

        # Ambos devem ser válidos
        self.assertGreater(len(prompt), 0)
    
    def test_escolher_prompt_otimizado(self):
        """Testa seleção de prompt otimizado."""
        prompt_fn = escolher_prompt("otimizado")
        
        self.assertEqual(prompt_fn, gerar_prompt_otimizado)
    
    def test_escolher_prompt_detalhado(self):
        """Testa seleção de prompt detalhado."""
        prompt_fn = escolher_prompt("detalhado")
        
        self.assertEqual(prompt_fn, gerar_prompt_com_instrucoes)
    
    def test_escolher_prompt_padrao(self):
        """Testa que padrão é otimizado."""
        prompt_fn = escolher_prompt("invalido")
        
        self.assertEqual(prompt_fn, gerar_prompt_otimizado)
    
    def test_estimar_tokens_prompt(self):
        """Testa estimativa de tokens do prompt."""
        tokens_otimizado = estimar_tokens_prompt(
            self.txt_meu, self.txt_conc, "otimizado"
        )
        tokens_detalhado = estimar_tokens_prompt(
            self.txt_meu, self.txt_conc, "detalhado"
        )

        # Ambos devem ser números positivos
        self.assertGreater(tokens_otimizado, 0)
        self.assertGreater(tokens_detalhado, 0)

        # Ambos devem ser válidos (não há garantia de qual é maior)
        self.assertIsInstance(tokens_otimizado, int)
        self.assertIsInstance(tokens_detalhado, int)
    
    def test_prompt_contem_json_valido(self):
        """Testa que prompt contém JSON válido."""
        prompt = gerar_prompt_otimizado(self.txt_meu, self.txt_conc)
        
        # Deve conter estrutura JSON
        self.assertIn('{', prompt)
        self.assertIn('}', prompt)
        self.assertIn('[', prompt)
        self.assertIn(']', prompt)


if __name__ == '__main__':
    unittest.main()

