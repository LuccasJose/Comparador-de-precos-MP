"""
Módulo de otimização de tokens para a API do Google Gemini.
Implementa cache, monitoramento e estratégias para manter dentro do limite gratuito.
"""
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

# Define o caminho da raiz do projeto (diretório pai de src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(PROJECT_ROOT, "dados_cache.json")
TOKEN_LOG_FILE = os.path.join(PROJECT_ROOT, "token_usage.json")

# Limite gratuito do Gemini: ~1M tokens/mês (aprox. 50k por execução semanal)
WEEKLY_TOKEN_LIMIT = 50000
WARNING_THRESHOLD = 0.8  # Avisar se usar 80% do limite


def calcular_hash_ocr(txt_meu: str, txt_conc: str, *, prompt: str = "") -> str:
    """Calcula hash do OCR (e opcionalmente do prompt) para detectar mudanças.

	    Incluimos o prompt no hash para evitar reutilizar cache antigo quando
	    as regras de extracao mudarem (melhorias de qualidade).
    """
    combined = f"{txt_meu}|{txt_conc}|PROMPT_V1|{prompt}"
    return hashlib.md5(combined.encode("utf-8", errors="ignore")).hexdigest()


def carregar_cache() -> Optional[Dict[str, Any]]:
    """Carrega dados em cache se existirem e forem recentes (< 7 dias)."""
    if not os.path.exists(CACHE_FILE):
        return None
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        # Verifica se o cache é recente (menos de 7 dias)
        timestamp = cache.get('timestamp')
        if timestamp:
            cache_date = datetime.fromisoformat(timestamp)
            if datetime.now() - cache_date < timedelta(days=7):
                return cache
    except Exception as e:
        print(f"⚠️  Erro ao carregar cache: {e}")
    
    return None


def salvar_cache(dados: Dict[str, Any], hash_ocr: str) -> None:
    """Salva dados em cache com timestamp e hash do OCR."""
    cache = {
        'timestamp': datetime.now().isoformat(),
        'hash_ocr': hash_ocr,
        'dados': dados
    }
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"💾 Cache salvo em {CACHE_FILE}")
    except Exception as e:
        print(f"⚠️  Erro ao salvar cache: {e}")


def verificar_mudanca_significativa(
    txt_meu: str,
    txt_conc: str,
    cache: Optional[Dict],
    *,
    prompt: str = "",
) -> bool:
    """Verifica se houve mudança significativa nos cardápios."""
    if cache is None:
        return True
    
    novo_hash = calcular_hash_ocr(txt_meu, txt_conc, prompt=prompt)
    hash_anterior = cache.get('hash_ocr', '')
    
    if novo_hash == hash_anterior:
        print("✅ Cardápios não mudaram. Reutilizando dados em cache.")
        return False
    
    print("🔄 Cardápios mudaram. Atualizando análise...")
    return True


def registrar_uso_tokens(tokens_usados: int, modelo: str) -> None:
    """Registra uso de tokens para monitoramento."""
    log = {}
    if os.path.exists(TOKEN_LOG_FILE):
        try:
            with open(TOKEN_LOG_FILE, 'r', encoding='utf-8') as f:
                log = json.load(f)
        except Exception:
            log = {}
    
    execucao = {
        'timestamp': datetime.now().isoformat(),
        'tokens': tokens_usados,
        'modelo': modelo
    }
    
    if 'execucoes' not in log:
        log['execucoes'] = []
    log['execucoes'].append(execucao)
    
    # Calcula total da semana
    agora = datetime.now()
    semana_passada = agora - timedelta(days=7)
    tokens_semana = sum(
        e['tokens'] for e in log['execucoes']
        if datetime.fromisoformat(e['timestamp']) > semana_passada
    )
    
    log['tokens_semana'] = tokens_semana
    log['limite_semanal'] = WEEKLY_TOKEN_LIMIT
    
    try:
        with open(TOKEN_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Erro ao registrar tokens: {e}")
    
    # Aviso se ultrapassar limite
    if tokens_semana > WEEKLY_TOKEN_LIMIT * WARNING_THRESHOLD:
        percentual = (tokens_semana / WEEKLY_TOKEN_LIMIT) * 100
        print(f"⚠️  AVISO: Consumo de tokens em {percentual:.1f}% do limite semanal!")


def exibir_resumo_tokens() -> None:
    """Exibe resumo do consumo de tokens."""
    if not os.path.exists(TOKEN_LOG_FILE):
        return
    
    try:
        with open(TOKEN_LOG_FILE, 'r', encoding='utf-8') as f:
            log = json.load(f)
        
        tokens_semana = log.get('tokens_semana', 0)
        limite = log.get('limite_semanal', WEEKLY_TOKEN_LIMIT)
        percentual = (tokens_semana / limite) * 100 if limite > 0 else 0
        
        print(f"\n📊 Consumo de tokens (últimos 7 dias):")
        print(f"   Usado: {tokens_semana:,} / {limite:,} ({percentual:.1f}%)")
    except Exception:
        pass

