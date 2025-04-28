.PHONY: migrate init revision upgrade downgrade run

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
	find . -type d -name "__pycache__" -exec rm -r {} +

# Comando para criar uma nova migração
alembic-migrate:
	alembic revision --autogenerate -m "$(message)" && alembic upgrade head

# Comando para resetar o banco de dados
alembic-reset:
	alembic downgrade base && alembic upgrade head

# Comando para forçar upgrade com CASCADE
alembic-upgrade-cascade:
	psql -U postgres -d a2a_saas -c "DROP TABLE IF EXISTS events CASCADE; DROP TABLE IF EXISTS sessions CASCADE; DROP TABLE IF EXISTS user_states CASCADE; DROP TABLE IF EXISTS app_states CASCADE;" && alembic upgrade head