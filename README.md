# Agent Runner API

API para execução de agentes de IA utilizando o Google ADK.

## Estrutura do Projeto

```
src/
├── api/          # Endpoints da API
├── core/         # Lógica central do negócio
├── models/       # Modelos de dados
├── schemas/      # Schemas Pydantic para validação
├── utils/        # Utilitários
├── config/       # Configurações
└── services/     # Serviços externos
```

## Requisitos

- Python 3.8+
- PostgreSQL
- OpenAI API Key

## Instalação

1. Clone o repositório:
```bash
git clone <url-do-repositorio>
cd a2a-saas
```

2. Crie um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

## Executando o Projeto

```bash
uvicorn src.main:app --reload
```

A API estará disponível em `http://localhost:8000`

## Documentação da API

A documentação interativa da API está disponível em:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Logs

Os logs são armazenados no diretório `logs/` com o seguinte formato:
- `{nome_do_logger}_{data}.log`

## Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request 