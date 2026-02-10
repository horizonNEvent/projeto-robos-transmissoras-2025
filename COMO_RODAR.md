# Como Rodar o Projeto (Backend e Frontend)

Este guia explica como executar os componentes da aplicação web (API Backend e Interface Frontend) localmente ou via Docker, conforme explicado no chat.

## Opção 1: Rodar Localmente (Recomendado para Desenvolvimento)

Nesta modalidade, você rodará os serviços diretamente na sua máquina. Você precisará de **dois terminais** abertos.

### 1. Backend (Terminal 1)
O Backend é construído com **FastAPI** (Python).

1.  Abra o terminal na raiz do projeto (`d:\Workspace\Tust-AETE`).
2.  Instale as dependências (caso ainda não tenha feito):
    ```powershell
    pip install -r app/backend/requirements.txt
    ```
3.  Inicie o servidor de desenvolvimento:
    ```powershell
    uvicorn app.backend.main:app --reload --port 8000
    ```
    *   A flag `--reload` permite que o servidor reinicie automaticamente ao salvar alterações no código.
    *   O Backend estará acessível em: `http://localhost:8000`.
    *   Documentação da API (Swagger): `http://localhost:8000/docs`.

### 2. Frontend (Terminal 2)
O Frontend é construído com **React** usando **Vite**.

1.  Navegue até a pasta do frontend:
    ```powershell
    cd app/frontend
    ```
2.  Instale as dependências Node (caso ainda não tenha feito):
    ```powershell
    npm install
    ```
3.  Inicie o servidor de desenvolvimento:
    ```powershell
    npm run dev
    ```
    *   O Frontend geralmente estará acessível em: `http://localhost:5173` (ou outra porta indicada no terminal).

---

## Opção 2: Rodar via Docker (Simples e Rápido)

Se você preferir rodar tudo em containers (isolado do seu ambiente local), pode utilizar o Docker Compose.

### Pré-requisitos
*   Docker e Docker Compose instalados.

### Comandos (via Makefile)
O projeto possui um `Makefile` na raiz para facilitar os comandos:

*   **Subir todo o ambiente**:
    ```powershell
    make up
    ```
    Isso executa `docker compose up -d` (modo detached/background).

*   **Parar o ambiente**:
    ```powershell
    make down
    ```

*   **Ver logs**:
    ```powershell
    make logs
    ```

*   **Reconstruir imagens** (útil se instalou novas dependências):
    ```powershell
    make build
    ```

---

## Resumo das Portas
*   **Frontend**: `5173` (Local)
*   **Backend API**: `8000`

---

## Compartilhar Acesso (Tunnel)

Para permitir que outra pessoa acesse seu projeto rodando localmente (via internet), você pode criar um "túnel". Isso expõe seu frontend para a web, permitindo que outros acessem como se estivessem na sua rede.

### Usando Localtunnel (Recomendado - Sem instalação)

Como seu frontend já está configurado para redirecionar as chamadas de API para o backend localmente, você só precisa expor a porta do frontend (**5173**).

1.  Certifique-se de que o **Frontend** (`npm run dev`) e o **Backend** (`uvicorn ...`) estão rodando.
2.  Abra um **novo terminal** (Terminal 3).
3.  Execute o seguinte comando:
    ```powershell
    npx localtunnel --port 5173
    ```
4.  O terminal exibirá uma URL (ex: `https://nome-aleatorio.loca.lt`).
5.  **Envie essa URL** para a pessoa.

**Atenção**: O `localtunnel` pode solicitar uma confirmação de segurança na primeira vez que a página for acessada. Geralmente, ele pede para digitar o endereço IP público de quem está hospedando (o seu). Você pode obter seu IP acessando [ipv4.icanhazip.com](https://ipv4.icanhazip.com) e passar para a pessoa, ou ela mesma verá instruçoes na tela.
