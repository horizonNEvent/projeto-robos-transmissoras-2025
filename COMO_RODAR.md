# Como Rodar o Projeto (Backend e Frontend)

Este guia explica como executar os componentes da aplicação web (API Backend e Interface Frontend) localmente ou via Docker, conforme explicado no chat.

## Opção 1: Rodar Localmente (Recomendado para Desenvolvimento)

Nesta modalidade, você rodará os serviços diretamente na sua máquina. Você precisará de **dois terminais** abertos.

### 1. Backend (Terminal 1)

O Backend é construído com **FastAPI** (Python).

1. Abra o terminal na raiz do projeto (`d:\Workspace\Tust-AETE`).
2. Instale as dependências (caso ainda não tenha feito):
   ```powershell
   pip install -r app/backend/requirements.txt
   ```
3. Inicie o servidor de desenvolvimento:
   ```powershell
   uvicorn app.backend.main:app --reload --port 8000
   ```

   * A flag `--reload` permite que o servidor reinicie automaticamente ao salvar alterações no código.
   * O Backend estará acessível em: `http://localhost:8000`.
   * Documentação da API (Swagger): `http://localhost:8000/docs`.

### 2. Frontend (Terminal 2)

O Frontend é construído com **React** usando **Vite**.

1. Navegue até a pasta do frontend:
   ```powershell
   cd app/frontend
   ```
2. Instale as dependências Node (caso ainda não tenha feito):
   ```powershell
   npm install
   ```
3. Inicie o servidor de desenvolvimento:
   ```powershell
   npm run dev
   ```

   * O Frontend geralmente estará acessível em: `http://localhost:5173` (ou outra porta indicada no terminal).

---

## Opção 2: Rodar via Docker (Simples e Rápido)

Se você preferir rodar tudo em containers (isolado do seu ambiente local), pode utilizar o Docker Compose.

### Pré-requisitos

* Docker e Docker Compose instalados.

### Comandos (via Makefile)

O projeto possui um `Makefile` na raiz para facilitar os comandos:

* **Subir todo o ambiente**:

  ```powershell
  make up
  ```

  Isso executa `docker compose up -d` (modo detached/background).
* **Parar o ambiente**:

  ```powershell
  make down
  ```
* **Ver logs**:

  ```powershell
  make logs
  ```
* **Reconstruir imagens** (útil se instalou novas dependências):

  ```powershell
  make build
  ```

---

## Resumo das Portas

* **Frontend**: `5173` (Local)
* **Backend API**: `8000`

---

## Compartilhar Acesso (Tunnel)

Para permitir que outra pessoa acesse seu projeto rodando localmente (via internet), você pode criar um "túnel". Isso expõe seu frontend para a web, permitindo que outros acessem como se estivessem na sua rede.

### Usando Cloudflare Tunnel (Mais robusto)

O Cloudflare Tunnel é uma alternativa excelente e gratuita para expor seu serviço. Você já possui o executável `cloudflared.exe` na raiz do projeto.

#### Opção A: Túnel Rápido (URL Temporária)

Útil para testes rápidos. Toda vez que você reiniciar, a URL mudará.

1. Certifique-se de que o **Frontend** (`npm run dev`) e o **Backend** (`uvicorn ...`) estão rodando.
2. Abra um **novo terminal** na raiz do projeto.
3. Execute o seguinte comando:
   ```powershell
   .\cloudflared.exe tunnel --url http://localhost:5173
   ```
4. Procure por uma linha no log que diga algo como:
   `https://algum-nome.trycloudflare.com`
5. **Envie essa URL** para a pessoa. O Cloudflare cuidará de encaminhar o tráfego para seu frontend e, através do proxy no `vite.config.js`, para seu backend.

#### Opção B: Túnel Permanente (Requer conta Cloudflare e Domínio)

Se você quiser uma URL fixa (ex: `meuprojeto.meudominio.com`), siga estes passos:

1. Crie uma conta gratuita em [dash.cloudflare.com](https://dash.cloudflare.com).
2. No terminal, faça login: `.\cloudflared.exe tunnel login`.
3. Crie um túnel: `.\cloudflared.exe tunnel create meu-projeto`.
4. Configure o DNS: `.\cloudflared.exe tunnel route dns meu-projeto meuprojeto.meudominio.com`.
5. Rode o túnel apontando para o frontend:
   ```powershell
   .\cloudflared.exe tunnel run --url http://localhost:5173 meu-projeto
   ```
