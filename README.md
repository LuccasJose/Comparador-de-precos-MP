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

# 1) Configure a API key do Gemini
# Local (Windows/Linux): crie um arquivo .env na raiz do projeto com:
#   GEMINI_API_KEY=...sua_chave...
# (o .env ja esta no .gitignore)

# GitHub Actions (ubuntu-latest):
# - Settings -> Secrets and variables -> Actions -> New repository secret
# - Name: GEMINI_API_KEY
# - Value: sua chave

# 2) Validacao rapida (sem chamar a API; sem custo)
python src/gemini_client.py --dry-run

# 3) Executar
python src/main.py