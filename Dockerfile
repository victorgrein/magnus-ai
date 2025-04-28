FROM python:3.10-slim

# Define o diretório de trabalho
WORKDIR /app

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Instala as dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -e .

# Configuração para produção
ENV PORT=8000 \
    HOST=0.0.0.0 \
    DEBUG=false

# Expose port
EXPOSE 8000

# Define o comando de inicialização
CMD alembic upgrade head && uvicorn src.main:app --host $HOST --port $PORT 