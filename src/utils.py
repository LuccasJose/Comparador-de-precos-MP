import pytesseract
from PIL import Image
import re
import os
import platform

# Configura o caminho do Tesseract de acordo com o SO
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# No Linux (GitHub Actions), o Tesseract é instalado via apt e está no PATH

def limpar_json_resposta(texto):
    """Remove marcações de markdown e tenta isolar o JSON da resposta da IA.

    O Gemini pode retornar o JSON dentro de blocos de codigo (```json ... ```)
    ou incluir texto extra. Esta funcao tenta:
    1) remover fences de markdown;
    2) extrair o primeiro objeto JSON entre '{' e '}'.
    """
    if texto is None:
        return ""

    t = str(texto).strip()

    # Remove fences no inicio/fim e quaisquer ocorrencias internas
    t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    t = re.sub(r"```[a-zA-Z0-9_-]*", "", t)
    t = t.replace("```", "").strip()

    # Tenta isolar o JSON (objeto) mesmo se vier com texto extra
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start : end + 1]

    return t.strip()

def extrair_texto_ocr(caminho_imagem):
    """Realiza OCR em uma imagem salva."""
    return pytesseract.image_to_string(Image.open(caminho_imagem), lang='por')