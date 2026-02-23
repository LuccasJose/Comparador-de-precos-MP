import pytesseract
from PIL import Image
import re
import os

# Coloca o caminho que ta no seu PC ai, se tiver errado não vai rodar 
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\tesseract.exe'

def limpar_json_resposta(texto):
    """Remove marcações de markdown da resposta da IA."""
    return re.sub(r'```json|```', '', texto).strip()

def extrair_texto_ocr(caminho_imagem):
    """Realiza OCR em uma imagem salva."""
    return pytesseract.image_to_string(Image.open(caminho_imagem), lang='por')