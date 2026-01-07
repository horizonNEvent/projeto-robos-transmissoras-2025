#!/bin/bash

# =================================================================
# Script de Deploy Automático - TUST Portal
# Instalação: Salve no servidor, dê permissão (chmod +x deploy.sh)
# Uso: ./deploy.sh
# =================================================================

echo "🚀 Iniciando deploy da nova versão..."

# 1. Atualiza o código fonte via Git (Puxa da branch atual)
echo "📥 Puxando atualizações do repositório..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git pull origin $CURRENT_BRANCH

# 2. Garante que os containers atuais parem (opcional, mas evita conflitos de porta na reconstrução)
# echo "🛑 Parando containers atuais..."
# docker-compose down

# 3. Constrói e reinicia os containers (Forçando build para pegar novos requirements)
echo "🏗️ Construindo imagens e iniciando containers..."
docker compose up -d --build --force-recreate

# 4. Limpeza de imagens antigas/órfãs para economizar espaço
echo "🧹 Limpando restos de builds antigos..."
docker image prune -f

echo "✅ Deploy finalizado com sucesso! O sistema está online."
echo "   - Backend: http://seu-servidor:8000"
echo "   - Frontend: http://seu-servidor:5173"
