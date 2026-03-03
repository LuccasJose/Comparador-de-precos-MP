import json
import os
import random
import re
import time
from typing import Any, Callable, Dict, Optional, Tuple


_PRICE_ONLY_RE = re.compile(r"^\s*(?i:(?:r\$\s*)?)[-+]?\d{1,6}([\.,:]\d{2})\s*$")
_HAS_LETTER_RE = re.compile(r"[A-Za-z\u00c0-\u00ff]")


def _looks_like_price_only(text: str) -> bool:
    if not text:
        return False
    return bool(_PRICE_ONLY_RE.match(str(text).strip()))


def _parse_price(value: Any) -> Optional[float]:
    """Best-effort parse price to float.

    Handles:
      - numbers
      - strings like "R$ 12,50", "12.50", "12,50", "242:98"
      - thousand separators in pt-BR ("1.234,56")
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            f = float(value)
        except Exception:
            return None
        return f if f == f else None  # not NaN

    if not isinstance(value, str):
        return None

    s = value.strip()
    if not s:
        return None

    s = re.sub(r"(?i)r\$\s*", "", s)
    s = s.replace(":", ".")
    # Se tiver ',' e '.', assume '.' como milhar e ',' como decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")

    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        f = float(s)
    except Exception:
        return None
    if f != f:
        return None
    return f


def sanitize_menu_payload(data: Any) -> Dict[str, Any]:
    """Normalize/sanitize Gemini output to the expected shape.

    - Ensures keys meu/conc exist
    - Filters invalid items (missing name/price, name without letters, name==price)
    - Parses price strings and rounds to 2 decimals
    """
    if not isinstance(data, dict):
        return {"meu": [], "conc": []}

    def norm_list(raw: Any) -> list:
        if not isinstance(raw, list):
            return []
        out = []
        for it in raw:
            if not isinstance(it, dict):
                continue
            name = str(it.get("n", "") or "").strip()
            price = _parse_price(it.get("p"))

            if not name:
                continue
            if not _HAS_LETTER_RE.search(name):
                # evita nomes que sao apenas numeros
                continue
            if _looks_like_price_only(name):
                continue
            if price is None:
                continue
            if price < 0:
                continue

            out.append({"n": name, "p": round(float(price), 2)})
        return out

    return {
        "meu": norm_list(data.get("meu")),
        "conc": norm_list(data.get("conc")),
    }

class GeminiIntegrationError(RuntimeError): pass
class GeminiAuthError(GeminiIntegrationError): pass
class GeminiRateLimitError(GeminiIntegrationError): pass
class GeminiNetworkError(GeminiIntegrationError): pass
class GeminiResponseError(GeminiIntegrationError): pass
class GeminiParseError(GeminiIntegrationError): pass
def _sanitize_for_log(text: str, max_len: int = 1200) -> str:
    text = text or ""
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    text = text.replace("\r", "")
    if len(text) > max_len:
        return text[:max_len] + "...<truncated>"
    return text

def require_gemini_api_key(env: Optional[Dict[str, str]] = None) -> str:
    """Return GEMINI_API_KEY or raise a clear auth/config error."""
    # Load .env robustly when reading from the real environment.
    # This makes local runs work even if executed from ./src (CWD != repo root).
    if env is None:
        dotenv_path = ""
        loaded = False
        try:
            from dotenv import load_dotenv, find_dotenv

            dotenv_path = find_dotenv(usecwd=False) or ""
            if dotenv_path:
                loaded = bool(load_dotenv(dotenv_path))
        except Exception:
            # dotenv is a convenience; env vars may still be set by the shell/CI.
            dotenv_path = ""
            loaded = False

    source = env if env is not None else os.environ
    api_key = (source.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        extra_hint = ""
        if env is None and dotenv_path:
            try:
                size = os.path.getsize(dotenv_path)
            except OSError:
                size = -1
            if size == 0:
                extra_hint = f" Arquivo .env encontrado em '{dotenv_path}', mas ele está vazio. Salve o arquivo com a linha GEMINI_API_KEY=..."
            elif not loaded:
                extra_hint = f" Arquivo .env encontrado em '{dotenv_path}', mas não foi possível carregá-lo (verifique permissões/formato)."
            else:
                extra_hint = f" Arquivo .env carregado de '{dotenv_path}', mas a chave não está definida nele."

        raise GeminiAuthError(
            "GEMINI_API_KEY não encontrada (vazia/ausente)."
            + extra_hint
            + " Local: crie/edite um arquivo .env na raiz com GEMINI_API_KEY=... (não commite)."
            + " GitHub Actions: configure o Secret GEMINI_API_KEY no repositório."
        )
    return api_key

def parse_gemini_json_response(raw_text: str) -> Tuple[Dict[str, Any], str]:
    """Parse Gemini response into a JSON dict. Returns (data, cleaned_json_str)."""
    # Local import to keep this module testable without heavy deps.
    try:
        from .utils import limpar_json_resposta
    except ImportError:
        from utils import limpar_json_resposta

    cleaned = limpar_json_resposta(raw_text or "")
    try:
        return json.loads(cleaned), cleaned
    except json.JSONDecodeError as e:
        preview = _sanitize_for_log(raw_text or "")
        cleaned_preview = _sanitize_for_log(cleaned)
        raise GeminiParseError(
            "Resposta do Gemini não é JSON válido após limpeza. "
            "Dica: ajuste o prompt para 'retorne APENAS JSON' ou use response_mime_type. "
            f"\n--- RAW (preview) ---\n{preview}"
            f"\n--- CLEANED (preview) ---\n{cleaned_preview}"
        ) from e


def _classify_exc(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    msg = str(exc).lower()

    if "unauth" in name or "permission" in name or ("api key" in msg and "invalid" in msg):
        return "auth"
    if "resourceexhausted" in name or "quota" in msg or "rate" in msg or "429" in msg:
        return "rate"
    if "timeout" in name or "deadline" in name or "timed out" in msg or "connection" in msg:
        return "network"
    return "other"


def generate_menu_json(
    prompt: str,
    *,
    model: Any = None,
    model_name: str = "gemini-2.5-flash-lite",
    timeout_seconds: int = 60,
    max_retries: int = 3,
    sleep_fn: Callable[[float], None] = time.sleep,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Call Gemini and return (parsed JSON dict, usage stats). If `model` is provided, no API key is needed."""
    if model is None:
        api_key = require_gemini_api_key(env)
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        # Ask for JSON when supported by the SDK/version.
        model = genai.GenerativeModel(
            model_name,
            generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
        )

    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            try:
                response = model.generate_content(prompt, request_options={"timeout": timeout_seconds})
            except TypeError:
                # Older versions may not support request_options
                response = model.generate_content(prompt)

            text = getattr(response, "text", None)
            if not text or not str(text).strip():
                raise GeminiResponseError("Gemini retornou resposta vazia (response.text vazio).")

            data, _cleaned = parse_gemini_json_response(str(text))
            data = sanitize_menu_payload(data)

            # Extrai informações de uso de tokens (se disponível)
            usage_metadata = getattr(response, "usage_metadata", None)
            if usage_metadata:
                prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0)
                output_tokens = getattr(usage_metadata, "output_token_count", 0)
            else:
                prompt_tokens = 0
                output_tokens = 0

            usage_stats = {
                "prompt_tokens": prompt_tokens,
                "response_tokens": output_tokens,
                "total_tokens": prompt_tokens + output_tokens,
                "modelo": model_name,
            }

            return data, usage_stats

        except GeminiIntegrationError:
            raise
        except Exception as exc:
            last_exc = exc
            kind = _classify_exc(exc)

            if kind in {"rate", "network"} and attempt < max_retries:
                # Exponential backoff + jitter
                delay = min(30.0, (2 ** (attempt - 1)) + random.random())
                sleep_fn(delay)
                continue

            if kind == "auth":
                raise GeminiAuthError(
                    "Falha de autenticação no Gemini. Verifique se a API key é válida e está ativa. "
                    "(Não exibimos a chave nos logs por segurança.)"
                ) from exc
            if kind == "rate":
                raise GeminiRateLimitError(
                    "Gemini retornou erro de cota/rate limit. Tente novamente mais tarde ou reduza chamadas."
                ) from exc
            if kind == "network":
                raise GeminiNetworkError(
                    "Falha de rede/timeout ao chamar o Gemini. Verifique conectividade e aumente o timeout."
                ) from exc

            raise GeminiIntegrationError(
                f"Falha inesperada ao chamar o Gemini ({exc.__class__.__name__}): {exc}"
            ) from exc

    raise GeminiIntegrationError(f"Falha ao chamar o Gemini após {max_retries} tentativas: {last_exc}")


def generate_menu_json_with_cache(
    prompt: str,
    txt_meu: str,
    txt_conc: str,
    **kwargs
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Wrapper que usa cache se disponível, senão chama Gemini."""
    try:
        from .token_optimizer import (
            carregar_cache, salvar_cache, verificar_mudanca_significativa,
            calcular_hash_ocr,
        )
    except ImportError:
        from token_optimizer import (
            carregar_cache, salvar_cache, verificar_mudanca_significativa,
            calcular_hash_ocr,
        )

    # Tenta carregar cache
    cache = carregar_cache()
    # Inclui prompt no hash para evitar reusar cache antigo quando regras do prompt mudarem.
    hash_ocr = calcular_hash_ocr(txt_meu, txt_conc, prompt=prompt)

    # Se cache existe e não houve mudança, reutiliza
    if cache and not verificar_mudanca_significativa(txt_meu, txt_conc, cache, prompt=prompt):
        dados = sanitize_menu_payload(cache.get('dados', {}))
        usage_stats = {
            "prompt_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "modelo": kwargs.get("model_name", "gemini-2.0-flash"),
            "fonte": "cache"
        }
        return dados, usage_stats

    # Senão, chama Gemini
    dados, usage_stats = generate_menu_json(prompt, **kwargs)
    dados = sanitize_menu_payload(dados)

    # Salva em cache
    salvar_cache(dados, hash_ocr)
    usage_stats["fonte"] = "gemini"

    return dados, usage_stats


if __name__ == "__main__":
    # Low-cost validation: only checks that env var exists (no API call).
    import argparse

    parser = argparse.ArgumentParser(description="Gemini integration quick checks")
    parser.add_argument("--dry-run", action="store_true", help="Only validate GEMINI_API_KEY presence")
    args = parser.parse_args()

    if args.dry_run:
        require_gemini_api_key()
        print("OK: GEMINI_API_KEY encontrada (dry-run).")

