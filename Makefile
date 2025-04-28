.PHONY: migrate init revision upgrade downgrade run seed-admin seed-client seed-agents seed-mcp-servers seed-tools seed-contacts seed-all docker-build docker-up docker-down docker-logs

# Comandos do Alembic
init:
	alembic init alembics

# make alembic-revision message="descrição da migração"
alembic-revision:
	alembic revision --autogenerate -m "$(message)"

# Comando para atualizar o banco de dados
alembic-upgrade:
	alembic upgrade head

# Comando para voltar uma versão
alembic-downgrade:
	alembic downgrade -1

# Comando para rodar o servidor
run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 --reload-dir src

# Comando para limpar o cache em todas as pastas do projeto pastas pycache
clear-cache:
	rm -rf ~/.cache/uv/environments-v2/* && find . -type d -name "__pycache__" -exec rm -r {} +

# Comando para criar uma nova migração
alembic-migrate:
	alembic revision --autogenerate -m "$(message)" && alembic upgrade head

# Comando para resetar o banco de dados
alembic-reset:
	alembic downgrade base && alembic upgrade head

# Comando para forçar upgrade com CASCADE
alembic-upgrade-cascade:
	psql -U postgres -d a2a_saas -c "DROP TABLE IF EXISTS events CASCADE; DROP TABLE IF EXISTS sessions CASCADE; DROP TABLE IF EXISTS user_states CASCADE; DROP TABLE IF EXISTS app_states CASCADE;" && alembic upgrade head

# Comandos para executar seeders
seed-admin:
	python -m scripts.seeders.admin_seeder

seed-client:
	python -m scripts.seeders.client_seeder

seed-agents:
	python -m scripts.seeders.agent_seeder

seed-mcp-servers:
	python -m scripts.seeders.mcp_server_seeder

seed-tools:
	python -m scripts.seeders.tool_seeder

seed-contacts:
	python -m scripts.seeders.contact_seeder

seed-all:
	python -m scripts.run_seeders

# Comandos Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-seed:
	docker-compose exec api python -m scripts.run_seeders