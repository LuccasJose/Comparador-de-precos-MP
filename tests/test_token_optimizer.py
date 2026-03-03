"""Testes para o módulo de otimização de tokens."""
import unittest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

# Adiciona src ao path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from token_optimizer import (
    calcular_hash_ocr,
    carregar_cache,
    salvar_cache,
    verificar_mudanca_significativa,
    registrar_uso_tokens,
)


class TestTokenOptimizer(unittest.TestCase):
    """Testes para otimização de tokens."""
    
    def setUp(self):
        """Prepara ambiente de teste."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_file = None
        self.original_log_file = None
    
    def tearDown(self):
        """Limpa arquivos temporários."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_calcular_hash_ocr(self):
        """Testa cálculo de hash do OCR."""
        txt1 = "Hambúrguer 25.50"
        txt2 = "Pizza 30.00"
        
        hash1 = calcular_hash_ocr(txt1, txt2)
        hash2 = calcular_hash_ocr(txt1, txt2)
        hash3 = calcular_hash_ocr(txt1, "Outro texto")
        
        # Mesmo texto deve gerar mesmo hash
        self.assertEqual(hash1, hash2)
        
        # Texto diferente deve gerar hash diferente
        self.assertNotEqual(hash1, hash3)
        
        # Hash deve ser string válida
        self.assertIsInstance(hash1, str)
        self.assertEqual(len(hash1), 32)  # MD5 tem 32 caracteres
    
    def test_cache_vazio(self):
        """Testa carregamento de cache quando arquivo não existe."""
        with patch('token_optimizer.CACHE_FILE', os.path.join(self.temp_dir, 'inexistente.json')):
            cache = carregar_cache()
            self.assertIsNone(cache)
    
    def test_salvar_e_carregar_cache(self):
        """Testa salvar e carregar cache."""
        cache_file = os.path.join(self.temp_dir, 'cache.json')
        
        with patch('token_optimizer.CACHE_FILE', cache_file):
            dados = {'meu': [{'n': 'Item', 'p': 10.0}], 'conc': []}
            hash_ocr = 'abc123'
            
            # Salva cache
            salvar_cache(dados, hash_ocr)
            self.assertTrue(os.path.exists(cache_file))
            
            # Carrega cache
            cache = carregar_cache()
            self.assertIsNotNone(cache)
            self.assertEqual(cache['hash_ocr'], hash_ocr)
            self.assertEqual(cache['dados'], dados)
    
    def test_cache_expirado(self):
        """Testa que cache expirado (> 7 dias) não é carregado."""
        cache_file = os.path.join(self.temp_dir, 'cache.json')
        
        # Cria cache com data antiga
        cache_antigo = {
            'timestamp': (datetime.now() - timedelta(days=8)).isoformat(),
            'hash_ocr': 'abc123',
            'dados': {}
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_antigo, f)
        
        with patch('token_optimizer.CACHE_FILE', cache_file):
            cache = carregar_cache()
            self.assertIsNone(cache)
    
    def test_verificar_mudanca_significativa(self):
        """Testa detecção de mudanças no OCR."""
        txt_meu = "Hambúrguer 25.50"
        txt_conc = "Pizza 30.00"
        
        # Sem cache, deve retornar True (mudança significativa)
        self.assertTrue(verificar_mudanca_significativa(txt_meu, txt_conc, None))
        
        # Com cache igual, deve retornar False
        cache = {
            'hash_ocr': calcular_hash_ocr(txt_meu, txt_conc),
            'dados': {}
        }
        self.assertFalse(verificar_mudanca_significativa(txt_meu, txt_conc, cache))
        
        # Com cache diferente, deve retornar True
        cache_diferente = {
            'hash_ocr': 'hash_diferente',
            'dados': {}
        }
        self.assertTrue(verificar_mudanca_significativa(txt_meu, txt_conc, cache_diferente))


if __name__ == '__main__':
    unittest.main()

