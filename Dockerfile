FROM python:3.11-slim

# Dependências de sistema para lxml e compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python antes de copiar o código (aproveita cache do Docker)
COPY pyproject.toml .
RUN pip install --no-cache-dir setuptools && pip install --no-cache-dir .

# Copia o restante do projeto
COPY . .

RUN mkdir -p /app/data && chmod +x /app/entrypoint.sh

EXPOSE 8000
