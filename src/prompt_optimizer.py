"""
Módulo com prompts otimizados para reduzir tokens.
Prompts concisos e diretos para o Gemini.
"""


def gerar_prompt_otimizado(txt_meu: str, txt_conc: str) -> str:
    """Gera prompt otimizado para extrair itens e preços com clareza."""
    return f"""Extraia itens+precos do OCR (pt-BR). Retorne APENAS JSON:
{{\"meu\":[{{\"n\":\"...\",\"p\":0.0}}],\"conc\":[{{\"n\":\"...\",\"p\":0.0}}]}}
Regras: n tem letras (nao e so preco). p=float 2 casas (25,50->25.50; 242:98->242.98). Preco sozinho -> linha anterior. Ignore preco solto.
MEU:\n{txt_meu}\nCONC:\n{txt_conc}"""


def gerar_prompt_com_instrucoes(txt_meu: str, txt_conc: str) -> str:
    """Gera prompt com instruções mais detalhadas (usa mais tokens)."""
    return f"""Você é um extrator de dados de cardápios.

TAREFA: Converter textos de OCR em JSON estruturado com itens e preços.

RETORNE APENAS JSON VÁLIDO (sem markdown/sem texto extra).
Esquema: {{"meu":[{{"n":"...","p":0.0}}],"conc":[{{"n":"...","p":0.0}}]}}

REGRAS:
1) "n" é nome legível do produto (deve conter letras). NÃO aceite "n" que seja só preço.
2) "p" é número (float) com 2 casas. Converta "12,50"→12.50 e "242:98"→242.98.
3) Se o preço estiver em linha separada, associe ao item mais próximo na linha anterior.
4) Ignore linhas que parecem apenas preço sem item associado.
5) Corrija erros comuns de OCR (O→0, S→5 etc.) quando fizer sentido.

MEU:
{txt_meu}

CONCORRENTE:
{txt_conc}"""


def escolher_prompt(modo: str = "otimizado") -> callable:
    """Retorna função de geração de prompt baseada no modo."""
    if modo == "otimizado":
        return gerar_prompt_otimizado
    elif modo == "detalhado":
        return gerar_prompt_com_instrucoes
    else:
        return gerar_prompt_otimizado  # padrão


def estimar_tokens_prompt(txt_meu: str, txt_conc: str, modo: str = "otimizado") -> int:
    """Estima tokens do prompt completo."""
    prompt_fn = escolher_prompt(modo)
    prompt = prompt_fn(txt_meu, txt_conc)
    # Estimativa: 1 token ≈ 4 caracteres
    return len(prompt) // 4

