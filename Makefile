# Makefile para Gerenciamento do Projeto TUST

.PHONY: help build up down restart logs ps deploy

help:
	@echo "Comandos disponíveis:"
	@echo "  make up       - Sobe os containers (Docker Compose)"
	@echo "  make build    - Reconstrói as imagens e sobe os containers"
	@echo "  make down     - Para e remove os containers"
	@echo "  make restart  - Reinicia os containers"
	@echo "  make logs     - Vê os logs em tempo real"
	@echo "  make ps       - Lista os containers"
	@echo "  make deploy   - (Executa no SERVIDOR) Pull e rebuild automatizado"

up:
	docker compose up -d

build:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

deploy:
	chmod +x deploy.sh
	./deploy.sh
