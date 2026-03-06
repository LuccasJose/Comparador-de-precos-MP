"""Testes para o módulo de otimização de OCR."""
import unittest
import os
import sys

# Adiciona src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ocr_optimizer import (
    limpar_ocr,
    extrair_itens_preco,
    extrair_itens_preco_com_contexto,
    resumir_ocr,
    estimar_tokens_ocr,
    comparar_tamanho_ocr,
)


class TestOCROptimizer(unittest.TestCase):
    """Testes para otimização de OCR."""
    
    def test_limpar_ocr_vazio(self):
        """Testa limpeza de OCR vazio."""
        self.assertEqual(limpar_ocr(""), "")
        self.assertEqual(limpar_ocr(None), "")
    
    def test_limpar_ocr_remove_linhas_vazias(self):
        """Testa remoção de linhas vazias."""
        ocr = "Hambúrguer\n\n\nPizza\n\n"
        resultado = limpar_ocr(ocr)
        
        linhas = resultado.split('\n')
        # Não deve ter linhas vazias
        self.assertNotIn("", linhas)
        self.assertIn("Hambúrguer", resultado)
        self.assertIn("Pizza", resultado)
    
    def test_limpar_ocr_remove_linhas_curtas(self):
        """Testa remoção de linhas muito curtas."""
        ocr = "a\nHambúrguer\nXY\nPizza"
        resultado = limpar_ocr(ocr)

        # Linhas com menos de 3 caracteres devem ser removidas
        linhas = resultado.split('\n')
        self.assertNotIn("a", linhas)
        self.assertNotIn("XY", linhas)
        self.assertIn("Hambúrguer", resultado)
    
    def test_extrair_itens_preco(self):
        """Testa extração de itens com preço."""
        ocr = """
        Hambúrguer
        Pizza 30.50
        Refrigerante
        Suco 5.00
        Sobremesa
        """
        resultado = extrair_itens_preco(ocr)
        
        # Deve manter apenas linhas com preço
        self.assertIn("Pizza 30.50", resultado)
        self.assertIn("Suco 5.00", resultado)
        self.assertNotIn("Hambúrguer\n", resultado)
    
    def test_extrair_itens_preco_sem_preco(self):
        """Testa extração quando não há preços."""
        ocr = "Hambúrguer\nPizza\nSuco"
        resultado = extrair_itens_preco(ocr)
        
        # Se não houver preços, retorna OCR original
        self.assertEqual(resultado, ocr)

    def test_extrair_itens_preco_com_contexto_pareia_linha_preco_sozinha(self):
        """Se o OCR separar NOME e PREÇO em linhas diferentes, deve juntar."""
        ocr = "X-Tudo\n16,00\nBatata frita\nR$ 12,50\n"
        resultado = extrair_itens_preco_com_contexto(ocr, contexto_preco=1, juntar_par=True)

        self.assertIn("X-Tudo 16,00", resultado)
        self.assertIn("Batata frita R$ 12,50", resultado)

    def test_extrair_itens_preco_com_contexto_prefere_nome_principal_antes_do_acompanhamento(self):
        ocr = (
            "Peito de Frango Grelhado (individual)\n"
            "Acompanha: Arroz branco, feijão tropeiro e banana à milanesa.\n"
            "R$ 71,06\n"
        )
        resultado = extrair_itens_preco_com_contexto(ocr, contexto_preco=1, juntar_par=True)

        self.assertIn("Peito de Frango Grelhado (individual) R$ 71,06", resultado)
        self.assertNotIn("Acompanha: Arroz branco, feijão tropeiro e banana à milanesa. R$ 71,06", resultado)

    def test_extrair_itens_preco_com_contexto_remove_ruido_de_pedido_minimo(self):
        ocr = "Pedido mín. R$ 50,00\nX-Tudo\nR$ 16,00\n"
        resultado = extrair_itens_preco_com_contexto(ocr, contexto_preco=1, juntar_par=True)

        self.assertNotIn("Pedido mín. R$ 50,00", resultado)
        self.assertIn("X-Tudo R$ 16,00", resultado)

    def test_resumir_ocr_modo_itens_preco_preserva_contexto(self):
        ocr = "X-Tudo\n16,00\nBatata frita\nR$ 12,50\nOutro texto sem preço\n"
        resultado = resumir_ocr(ocr, max_linhas=100, modo="itens_preco", contexto_preco=1)
        # Deve conter pares item+preço em uma linha
        self.assertIn("X-Tudo 16,00", resultado)
        self.assertIn("Batata frita R$ 12,50", resultado)
    
    def test_estimar_tokens_ocr(self):
        """Testa estimativa de tokens."""
        # 1 token ≈ 4 caracteres
        texto = "a" * 400  # 400 caracteres
        tokens = estimar_tokens_ocr(texto)
        
        self.assertEqual(tokens, 100)  # 400 / 4 = 100
    
    def test_resumir_ocr_trunca_grande(self):
        """Testa truncamento de OCR muito grande."""
        # Cria OCR com 150 linhas
        linhas = [f"Item {i} {10.0 + i}" for i in range(150)]
        ocr = '\n'.join(linhas)
        
        resultado = resumir_ocr(ocr, max_linhas=100)
        
        # Deve ter no máximo 100 linhas
        resultado_linhas = resultado.split('\n')
        self.assertLessEqual(len(resultado_linhas), 100)
    
    def test_comparar_tamanho_ocr(self):
        """Testa comparação de tamanho de OCR."""
        txt_meu = "Hambúrguer 25.50\nPizza 30.00"
        txt_conc = "Hambúrguer 24.00\nPizza 29.50"
        
        txt_meu_opt, txt_conc_opt, tokens_est = comparar_tamanho_ocr(txt_meu, txt_conc)
        
        # Deve retornar strings otimizadas
        self.assertIsInstance(txt_meu_opt, str)
        self.assertIsInstance(txt_conc_opt, str)
        
        # Deve retornar estimativa de tokens
        self.assertIsInstance(tokens_est, int)
        self.assertGreater(tokens_est, 0)


if __name__ == '__main__':
    unittest.main()

