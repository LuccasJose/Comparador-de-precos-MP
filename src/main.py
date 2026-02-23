import os
import json
import re
import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import google.generativeai as genai
from thefuzz import fuzz, process
from utils import limpar_json_resposta, extrair_texto_ocr

# Carrega a chave do arquivo .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def capturar_menu(url, rotulo):
    """Navega no Livemenu, rola a página e tira print para OCR."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Scroll para carregar pratos dinâmicos (essencial no Livemenu/Beta)
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)
            
        img_path = f"temp_{rotulo}.png"
        page.screenshot(path=img_path, full_page=True)
        browser.close()
        
        texto = extrair_texto_ocr(img_path)
        if os.path.exists(img_path):
            os.remove(img_path)
        return texto

def comparar(url_meu, url_conc):
    print("Iniciando captura dos cardápios...")
    txt_meu = capturar_menu(url_meu, "meu_restaurante")
    txt_conc = capturar_menu(url_conc, "concorrente")

    # --- O PROMPT QUE FALTAVA ---
    # Este prompt instrui a IA a estruturar o 'lixo' do OCR em dados limpos.
    prompt = f"""
    Aja como um extrator de dados de cardápios.
    OBJETIVO: Converter os textos brutos de OCR abaixo em um JSON estruturado.
    
    REGRAS:
    1. Identifique apenas NOME DO ITEM e PREÇO.
    2. Converta preços para float (ex: 12.50).
    3. Corrija erros de OCR (ex: 'O' para 0, 'S' para 5).
    4. Retorne APENAS o JSON no formato: 
       {{"meu": [{{"n": "item", "p": 0.0}}], "conc": [{{"n": "item", "p": 0.0}}]}}

    TEXTO A (Meu Restaurante):
    {txt_meu}

    TEXTO B (Concorrente):
    {txt_conc}
    """
    
    print("Solicitando análise à Inteligência Artificial...")
    response = model.generate_content(prompt)
    
    # Limpa e converte a resposta para dicionário Python
    dados = json.loads(limpar_json_resposta(response.text))

    # Lógica de Comparação com Fuzzy Matching
    meus_prods = {i['n']: i['p'] for i in dados['meu']}
    relatorio = []

    for item_c in dados['conc']:
        # Busca o item mais similar no seu cardápio
        match, score = process.extractOne(item_c['n'], meus_prods.keys(), scorer=fuzz.token_sort_ratio) or (None, 0)
        
        if score >= 65: # Limite de similaridade para considerar o mesmo produto
            preco_meu = meus_prods[match]
            relatorio.append({
                "Concorrente": item_c['n'],
                "Meu Item": match,
                "Preço Conc": item_c['p'],
                "Meu Preço": preco_meu,
                "Diferença": round(preco_meu - item_c['p'], 2),
                "Status": "Caro" if preco_meu > item_c['p'] else "Barato"
            })
            
    return relatorio

if __name__ == "__main__":
    # Luccas, coloque seus links reais aqui para testar
    LINK_MEU = "https://livemenu.app/menu/64e37fc6a53f6d0056007d55"
    LINK_CONC = "https://beta.livemenu.app/menu/loja-concorrente"
    
    try:
        resultado = comparar(LINK_MEU, LINK_CONC)
        df = pd.DataFrame(resultado)
        df.to_excel("comparativo_precos.xlsx", index=False)
        print("\n=== SUCESSO! ===")
        print("Planilha 'comparativo_precos.xlsx' gerada com sucesso.")
    except Exception as e:
        print(f"Erro ao processar: {e}")