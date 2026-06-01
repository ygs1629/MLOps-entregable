# Imagen multi-stage build para reducir peso y aumentar velocidad en el registro

# Imagen de python usada solo para la instalación de dependencias
FROM python:3.13-slim AS builder

# Instalar uv directamente
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copiar solo dependencias primero para aprovechar caché
COPY pyproject.toml uv.lock ./

# Instalar las dependencias del proyecto
RUN uv sync --frozen --no-dev

# Imagen final de ejecución. Solo usa el entorno creado por la imagen anterior de python
FROM python:3.13-slim

WORKDIR /app

# copiar el entorno ya creado 
COPY --from=builder /app/.venv /app/.venv

# Copiar el código la app
COPY ecominsight_agent /app/ecominsight_agent

# usar el entorno como variable de entorno para la ejecución de la imagen dentro del contenedor
ENV PATH="/app/.venv/bin:$PATH"

# Comando para arrancar el agente dentro del contenedor
CMD ["python", "-m", "ecominsight_agent.agent"]