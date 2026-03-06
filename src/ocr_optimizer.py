"""src.ocr_optimizer

O objetivo aqui é reduzir tokens **sem destruir** a estrutura do menu.
O erro mais comum do OCR é separar NOME e PREÇO em linhas diferentes.
Se extraímos apenas linhas com preço, o Gemini pode receber somente números
e gerar JSON com `n` sendo o próprio preço.
"""

import re
from typing import Tuple


# Match comum de preço com 2 casas; aceita ',', '.' e ':' (OCR às vezes troca por ':')
_PRICE_RE = re.compile(r"[0-9]{1,6}([\.,:][0-9]{2})")
_HAS_LETTER_RE = re.compile(r"[A-Za-zÀ-ÿ]")
_NOISE_PREFIXES = (
    "pedido mín",
    "pedido min",
    "perfil da loja",
    "loja offline",
    "offline",
)
_SECTION_PREFIXES = (
    "completos para",
    "cortes da casa",
    "peixes e frutos do mar",
    "risotos",
    "massas",
    "saladas",
    "kids",
    "petiscos",
    "espetinhos",
)


def limpar_ocr(texto: str) -> str:
    """Remove ruído e linhas vazias do OCR."""
    if not texto:
        return ""
    
    # Remove linhas vazias e espaços extras
    linhas = [linha.strip() for linha in str(texto).split('\n')]
    # Remove linhas muito curtas/sem informação (mas evita remover preços como "9,90")
    linhas = [l for l in linhas if l and (len(l) > 2 or _PRICE_RE.search(l))]
    
    # Remove caracteres de controle e símbolos estranhos
    texto_limpo = '\n'.join(linhas)
    texto_limpo = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', texto_limpo)
    # Normaliza espaços
    texto_limpo = re.sub(r"[ \t]{2,}", " ", texto_limpo)
    
    return texto_limpo


def _is_price_only_line(linha: str) -> bool:
    """True se a linha parece ser *apenas* um preço (sem nome)."""
    if not linha:
        return False
    s = linha.strip()
    s = re.sub(r"(?i)r\$\s*", "", s)
    s = s.replace(" ", "")
    # remove separadores de milhar comuns (ex: 1.234,56)
    # (mantemos o último separador como decimal)
    # Heurística: se tem mais de um '.', remove todos
    if s.count('.') > 1 and ',' in s:
        s = s.replace('.', '')
    # aceita ':', ',', '.' como separador decimal
    return bool(re.fullmatch(r"[-+]?[0-9]{1,6}([\.,:][0-9]{2})", s))


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _is_noise_line(linha: str) -> bool:
    texto = _normalize_text(linha)
    return any(texto.startswith(prefixo) for prefixo in _NOISE_PREFIXES)


def _score_name_candidate(linha: str) -> int:
    texto = (linha or "").strip()
    if not texto or not _HAS_LETTER_RE.search(texto):
        return -999
    if _is_price_only_line(texto) or _is_noise_line(texto):
        return -999

    normalizado = _normalize_text(texto)
    palavras = [p for p in re.findall(r"[A-Za-zÀ-ÿ0-9]+", texto) if _HAS_LETTER_RE.search(p)]
    ratio_titulo = 0.0
    if palavras:
        ratio_titulo = sum(1 for p in palavras if p[:1].isupper()) / len(palavras)

    score = 0
    if len(texto) <= 70:
        score += 2
    elif len(texto) >= 120:
        score -= 2

    virgulas = texto.count(',')
    if virgulas == 0:
        score += 2
    elif virgulas >= 2:
        score -= 2

    if re.search(r"[\.:;]$", texto):
        score -= 1
    else:
        score += 1

    if len(palavras) <= 8:
        score += 1
    elif len(palavras) >= 14:
        score -= 1

    if ratio_titulo >= 0.6:
        score += 2
    elif ratio_titulo < 0.35:
        score -= 1

    if normalizado.startswith(("acompanha", "acompanha:", "(serve", "(espetinho", "(penne", "(sem")):
        score -= 6
    if any(normalizado.startswith(prefixo) for prefixo in _SECTION_PREFIXES):
        score -= 4

    return score


def _pick_name_before_price(linhas, idx_preco: int, contexto_preco: int, used_names=None) -> str:
    limite = max(3, int(contexto_preco) + 2)
    candidatos = []

    j = idx_preco - 1
    while j >= 0 and len(candidatos) < limite:
        cand = (linhas[j] or "").strip()
        j -= 1
        if not cand:
            continue
        if _PRICE_RE.search(cand) and not _HAS_LETTER_RE.search(cand):
            continue
        if used_names and cand in used_names:
            continue
        candidatos.append(cand)

    melhor = ""
    melhor_score = -999
    for pos, cand in enumerate(candidatos):
        score = _score_name_candidate(cand)
        # Bônus de proximidade: candidatos mais próximos do preço são preferidos
        score += max(0, 4 - pos * 2)
        if score > melhor_score:
            melhor = cand
            melhor_score = score

    if melhor:
        return melhor
    return candidatos[0] if candidatos else ""


def extrair_itens_preco_com_contexto(texto: str, contexto_preco: int = 1, juntar_par: bool = True) -> str:
    """Extrai linhas com preço e preserva o contexto (ex.: nome na linha anterior).

    - Se a linha for apenas preço, inclui a(s) linha(s) anterior(es) como nome.
    - `contexto_preco` controla quantas linhas anteriores podem ser usadas.
    - `juntar_par=True` produz linhas no formato "NOME PREÇO", ótimo para o prompt.
    """
    if not texto:
        return ""

    linhas = [l.strip() for l in str(texto).split('\n')]
    out = []

    def add_line(s: str) -> None:
        s = (s or "").strip()
        if not s:
            return
        if not out or out[-1] != s:
            out.append(s)

    used_names = set()

    for i, linha in enumerate(linhas):
        if not linha:
            continue
        if not _PRICE_RE.search(linha):
            continue
        if _is_noise_line(linha):
            continue

        if _is_price_only_line(linha):
            # procura um possível nome nas linhas anteriores, preferindo títulos
            nome = _pick_name_before_price(linhas, i, contexto_preco, used_names)

            if nome:
                used_names.add(nome)
            if nome and juntar_par:
                add_line(f"{nome} {linha}".strip())
            else:
                if nome:
                    add_line(nome)
                add_line(linha)
        else:
            add_line(linha)

    return '\n'.join(out) if out else str(texto)


def extrair_itens_preco(texto: str) -> str:
    """Extrai apenas linhas que parecem ser itens + preços."""
    if not texto:
        return ""
    
    linhas = texto.split('\n')
    itens = []
    
    for linha in linhas:
        # Procura por padrões: "Nome ... Preço" ou "Nome Preço"
        # Preços geralmente têm números com ponto/vírgula
        if re.search(r'\d+[\.,:]\d{2}', linha):
            itens.append(linha.strip())
    
    return '\n'.join(itens) if itens else texto


def resumir_ocr(
    texto: str,
    max_linhas: int = 100,
    modo: str = "itens_preco",
    contexto_preco: int = 3,
    min_itens_fallback: int = 1,
) -> str:
    """Reduz OCR a um máximo de linhas, preservando pares item↔preço.

    `modo`:
      - "itens_preco": tenta manter apenas itens com preço + contexto (default)
      - "completo": usa o texto limpo completo (truncado)
    """
    if not texto:
        return ""
    
    # Primeiro, limpa o OCR
    texto = limpar_ocr(texto)
    
    modo = (modo or "itens_preco").strip().lower()

    if modo in {"itens_preco", "itens+preco", "itens", "pares"}:
        extraido = extrair_itens_preco_com_contexto(
            texto,
            contexto_preco=contexto_preco,
            juntar_par=True,
        )
        # Fallback: se extração ficou pequena demais (provável falta de decimais / OCR ruim),
        # volta ao texto completo (ainda limpo) para não perder nomes.
        if len([l for l in extraido.split('\n') if l.strip()]) < int(min_itens_fallback):
            texto = texto
        else:
            texto = extraido
    else:
        # "completo" ou qualquer outro valor
        texto = texto
    
    # Se ainda estiver muito grande, trunca.
    # Estratégia: mantém início e fim para não perder itens se o cardápio estiver no "fim" do OCR.
    linhas = texto.split('\n')
    if len(linhas) > max_linhas:
        print(f"⚠️  OCR muito grande ({len(linhas)} linhas). Truncando para {max_linhas}...")
        max_linhas = int(max_linhas)
        head = max_linhas // 2
        tail = max_linhas - head
        selecionadas = linhas[:head] + linhas[-tail:]
        # remove vazias e duplicadas adjacentes
        compact = []
        for l in selecionadas:
            l = (l or "").strip()
            if not l:
                continue
            if compact and compact[-1] == l:
                continue
            compact.append(l)
        texto = '\n'.join(compact)
    
    return texto


def estimar_tokens_ocr(texto: str) -> int:
    """Estima tokens do texto OCR (aprox. 1 token = 4 caracteres)."""
    return len(texto) // 4


def comparar_tamanho_ocr(
    txt_meu: str,
    txt_conc: str,
    *,
    max_linhas: int = 100,
    modo: str = "itens_preco",
    contexto_preco: int = 3,
    min_itens_fallback: int = 1,
) -> Tuple[str, str, int]:
    """Otimiza ambos os OCRs e retorna resumo + estimativa de tokens."""
    txt_meu_opt = resumir_ocr(
        txt_meu,
        max_linhas=max_linhas,
        modo=modo,
        contexto_preco=contexto_preco,
        min_itens_fallback=min_itens_fallback,
    )
    txt_conc_opt = resumir_ocr(
        txt_conc,
        max_linhas=max_linhas,
        modo=modo,
        contexto_preco=contexto_preco,
        min_itens_fallback=min_itens_fallback,
    )
    
    tokens_est = estimar_tokens_ocr(txt_meu_opt) + estimar_tokens_ocr(txt_conc_opt)
    
    print(f"📝 OCR otimizado:")
    print(f"   Meu restaurante: {len(txt_meu_opt)} chars (~{estimar_tokens_ocr(txt_meu_opt)} tokens)")
    print(f"   Concorrente: {len(txt_conc_opt)} chars (~{estimar_tokens_ocr(txt_conc_opt)} tokens)")
    print(f"   Total estimado: ~{tokens_est} tokens")
    
    return txt_meu_opt, txt_conc_opt, tokens_est

