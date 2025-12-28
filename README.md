# Projeto Robôs Transmissoras 2025 (TUST AETE)

Este projeto contém uma coleção de robôs de automação desenvolvidos em Python para o download, organização e processamento de documentos de faturamento (**TUST**) de diversas transmissoras de energia elétrica.

## Funcionalidades

- **Download Automático**: Captura XML, DANFE e Boletos de portais como SigetPlus, Portal do Cliente Eletrobras, entre outros.
- **Integração com Outlook**: Script para baixar anexos de e-mails específicos usando OAuth2. (TODO)
- **Conversão de Documentos**: Converte boletos em formato HTML para PDF utilizando `pdfkit`.
- **Padronização**: Organiza os arquivos baixados em uma estrutura de pastas hierárquica por Empresa e Código ONS.(TODO)
📂 Estrutura de Pastas
Data/: Arquivos JSON com credenciais, mapeamentos de CNPJ e listas de empresas.
Email/: Scripts e configurações para automação via Outlook/IMAP.
IE/: Componentes base para os robôs.

## Tecnologias Utilizadas

- **Python 3.10+**
- **Requests & BeautifulSoup4**: Para navegação Web e Parsing de HTML.
- **Playwright**: Para automação de portais que requerem interação com navegador (ex: Furnas).
- **PDFKit**: Para geração de PDFs a partir de fontes HTML.

## Pré-requisitos

### 1. Dependências do Python
Instale as bibliotecas necessárias:
```powershell
pip install -r requirements.txt

### 2. Configuração do PDFKit
Configure o PDFKit para converter HTML para PDF:
```powershell
pdfkit.configure(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
```

### 3. Configuração do Playwright
Configure o Playwright para converter HTML para PDF:
```powershell
playwright install
```
