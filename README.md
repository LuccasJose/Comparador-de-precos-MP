# Comparador de Preços Livemenu(atualmente) (OCR + IA)

Este projeto automatiza a comparação de preços entre restaurantes que utilizam a plataforma Livemenu (incluindo versões Beta).

## 🚀 Tecnologias
- **Python**
- **Playwright** (Navegação dinâmica)
- **Tesseract OCR** (Extração de texto de imagens)
- **Google Gemini API** (Estruturação de dados)
- **TheFuzz** (Fuzzy Matching para comparação de nomes similares)

## 📋 Pré-requisitos
1. Instale o [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) no seu Windows.
2. Obtenha uma API Key no Google AI Studio.

## 🛠️ Instalação
```bash
pip install -r requirements.txt
python -m playwright install chromium