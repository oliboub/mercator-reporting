FROM python:3.11-slim

# uv depuis l'image officielle Astral
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# uv installe dans le Python système du container
ENV UV_SYSTEM_PYTHON=1

# Copie des fichiers de dépendances en premier (layer cache Docker)
COPY pyproject.toml README.md ./

# Installation des dépendances (production uniquement)
# uv pip install -e . lit pyproject.toml correctement
RUN uv pip install -e . --no-cache

# Copie du code source APRÈS les dépendances (optimise le cache)
COPY src/ ./src/
COPY scripts/ ./scripts/

# Répertoire de stockage des rapports sauvegardés
RUN mkdir -p /app/storage

VOLUME ["/app/storage"]
EXPOSE 8000

# ARG pour distinguer dev (--reload) et prod (sans reload)
ARG ENV=dev

# Dev : --reload activé (hot reload via volume ./src:/app/src)
# Prod : sans --reload, sans exposition inutile
CMD if [ "$ENV" = "prod" ]; then \
      uvicorn src.main:app --host 0.0.0.0 --port 8000; \
    else \
      uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload; \
    fi