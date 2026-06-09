.DEFAULT_GOAL := help

.env:
	@cp .env.example .env
	@echo ""
	@echo "  Arquivo .env criado. Edite OPENAI_API_KEY e OPENAI_MODEL."
	@echo ""

.PHONY: up
up: .env data          ## Constrói e sobe todos os containers (web + scheduler)
	docker compose up --build -d
	@echo ""
	@echo "  SelectorWatch  →  http://localhost:8000"
	@echo "  Admin Django   →  http://localhost:8000/admin"
	@echo ""
	@echo "  Próximos passos:"
	@echo "    make superuser      criar login para o admin"
	@echo "    make add-site       cadastrar site de exemplo"
	@echo "    make logs           acompanhar logs de todos os containers"
	@echo ""

.PHONY: down
down:                  ## Para e remove os containers
	docker compose down

.PHONY: restart
restart:               ## Reinicia os containers sem rebuild
	docker compose restart

.PHONY: logs
logs:                  ## Exibe logs em tempo real de todos os containers
	docker compose logs -f

.PHONY: logs-web
logs-web:              ## Logs apenas do container web
	docker compose logs -f web

.PHONY: logs-scheduler
logs-scheduler:        ## Logs apenas do scheduler
	docker compose logs -f scheduler

.PHONY: build
build:                 ## Reconstrói as imagens sem subir
	docker compose build

.PHONY: superuser
superuser:             ## Cria superusuário para acessar o admin Django
	docker compose exec web python manage.py createsuperuser

.PHONY: shell
shell:                 ## Abre o shell interativo do Django
	docker compose exec web python manage.py shell

.PHONY: add-site
add-site:              ## Cadastra um site de exemplo (books.toscrape.com)
	docker compose exec web python manage.py add_site \
	  --name "Books to Scrape (exemplo)" \
	  --url "https://books.toscrape.com" \
	  --interval 30
	docker compose exec web python manage.py add_selector \
	  --site-id 1 \
	  --name "Preco do primeiro livro" \
	  --selector ".price_color" \
	  --type css \
	  --expected number
	@echo "Site e seletor de exemplo criados."

.PHONY: check
check:                 ## Verifica todos os seletores manualmente agora
	docker compose exec web python manage.py check_selectors

.PHONY: diagnose
diagnose:              ## Diagnostica seletor + LLM (uso: make diagnose ID=1)
	docker compose exec web python manage.py diagnose_selector $(ID)

.PHONY: migrate
migrate:               ## Aplica migrations manualmente
	docker compose exec web python manage.py migrate

.PHONY: data
data:
	@mkdir -p data

.PHONY: clean
clean:                 ## Para containers e remove volumes e imagens do projeto
	docker compose down --volumes --rmi local

.PHONY: help
help:
	@echo ""
	@echo "  SelectorWatch — Comandos disponíveis"
	@echo "  ──────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
