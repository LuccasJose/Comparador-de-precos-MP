import os
import json
import re
import argparse
import pandas as pd
from dotenv import load_dotenv, find_dotenv
from thefuzz import fuzz, process

try:
    from .gemini_client import GeminiIntegrationError, generate_menu_json_with_cache
    from .ocr_optimizer import comparar_tamanho_ocr
    from .token_optimizer import registrar_uso_tokens, exibir_resumo_tokens
except ImportError:
    from gemini_client import GeminiIntegrationError, generate_menu_json_with_cache
    from ocr_optimizer import comparar_tamanho_ocr
    from token_optimizer import registrar_uso_tokens, exibir_resumo_tokens

load_dotenv(find_dotenv(usecwd=False))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def capturar_menu(url, timeout_seconds=30, headless=True):
    from playwright.sync_api import sync_playwright
    timeout_ms = timeout_seconds * 1000
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        try:
            page.wait_for_selector("[data-price], .menu-item, .item, [class*='price']", timeout=5000)
        except Exception:
            pass
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)
        texto = page.inner_text("body")
        browser.close()
        return texto

def comparar(url_meu, url_conc, timeout_seconds=30, headless=True):
    print("Iniciando captura dos cardapios...")
    txt_meu = capturar_menu(url_meu, timeout_seconds=timeout_seconds, headless=headless)
    txt_conc = capturar_menu(url_conc, timeout_seconds=timeout_seconds, headless=headless)

    print("Otimizando OCR para reduzir tokens...")
    ocr_max_linhas = int(os.getenv("OCR_MAX_LINHAS", "100"))
    ocr_modo = os.getenv("OCR_MODE", "itens_preco")
    ocr_contexto_preco = int(os.getenv("OCR_PRECO_CONTEXTO", "3"))
    ocr_min_itens_fallback = int(os.getenv("OCR_MIN_ITENS_FALLBACK", "1"))

    txt_meu_opt, txt_conc_opt, tokens_est_ocr = comparar_tamanho_ocr(
        txt_meu,
        txt_conc,
        max_linhas=ocr_max_linhas,
        modo=ocr_modo,
        contexto_preco=ocr_contexto_preco,
        min_itens_fallback=ocr_min_itens_fallback,
    )

    prompt_mode = os.getenv("GEMINI_PROMPT_MODE", "otimizado")
    try:
        from .prompt_optimizer import escolher_prompt
    except ImportError:
        from prompt_optimizer import escolher_prompt
    prompt_fn = escolher_prompt(prompt_mode)
    prompt = prompt_fn(txt_meu_opt, txt_conc_opt)

    print(f"Enviando para Gemini (prompt estimado: ~{len(prompt)//4} tokens)...")
    try:
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
        max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3"))

        dados, usage_stats = generate_menu_json_with_cache(
            prompt,
            txt_meu_opt,
            txt_conc_opt,
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        fonte = usage_stats.get("fonte", "gemini")
        total_tokens = usage_stats.get("total_tokens", 0)

        if fonte == "cache":
            print("Dados carregados do cache (0 tokens gastos)")
        else:
            print("Resposta recebida do Gemini")
            print(f"   Tokens usados: {total_tokens} (prompt: {usage_stats.get('prompt_tokens', 0)}, resposta: {usage_stats.get('response_tokens', 0)})")
            registrar_uso_tokens(total_tokens, model_name)

    except GeminiIntegrationError as e:
        print(f"Falha na etapa de IA (Gemini): {e}")
        raise

    fuzzy_threshold = int(os.getenv("FUZZY_THRESHOLD", "65"))
    meus_prods = {i['n']: i['p'] for i in dados['meu']}
    relatorio = []

    for item_c in dados['conc']:
        match, score = process.extractOne(item_c['n'], meus_prods.keys(), scorer=fuzz.token_sort_ratio) or (None, 0)

        if score >= fuzzy_threshold:
            preco_meu = meus_prods[match]
            relatorio.append({
                "Concorrente": item_c['n'],
                "Meu Item": match,
                "Preco Conc": item_c['p'],
                "Meu Preco": preco_meu,
                "Diferenca": round(preco_meu - item_c['p'], 2),
                "Status": "Caro" if preco_meu > item_c['p'] else "Barato"
            })

    return relatorio, dados

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compara precos de cardapios entre dois restaurantes usando Playwright e Gemini"
    )
    parser.add_argument("--url-meu", required=True, help="URL do seu restaurante (obrigatorio)")
    parser.add_argument("--url-conc", required=True, help="URL do restaurante concorrente (obrigatorio)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout em segundos para Playwright (padrao: 30)")
    parser.add_argument("--headless", type=lambda x: x.lower() in ("true", "1", "yes"), default=True, help="Executar navegador em modo headless (padrao: True)")

    args = parser.parse_args()

    try:
        resultado, dados = comparar(
            args.url_meu,
            args.url_conc,
            timeout_seconds=args.timeout,
            headless=args.headless
        )

        dados_json_path = os.path.join(PROJECT_ROOT, 'dados.json')
        with open(dados_json_path, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print(f"Arquivo 'dados.json' gerado com sucesso em {dados_json_path}")

        comparativo_xlsx_path = os.path.join(PROJECT_ROOT, 'comparativo_precos.xlsx')
        df = pd.DataFrame(resultado)
        df.to_excel(comparativo_xlsx_path, index=False)
        print(f"Planilha 'comparativo_precos.xlsx' gerada com sucesso em {comparativo_xlsx_path}")

        print("=== SUCESSO ===")
        print("Todos os arquivos foram gerados com sucesso.")

        exibir_resumo_tokens()

    except ValueError as e:
        print(f"Erro de configuracao: {e}")
        exit(1)
    except Exception as e:
        print(f"Erro ao processar: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
