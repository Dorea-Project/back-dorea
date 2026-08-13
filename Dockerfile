# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv : installateur/gestionnaire de dépendances
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ⚠️ **LibreOffice, et rien de plus.** Le PDF du livrable Urim est une CONVERSION du
# fichier déjà validé — jamais une seconde mise en page, qui dériverait en silence.
# `--no-install-recommends` et les deux seuls composants utiles (Writer pour la note,
# Impress pour les diapositives) : la suite complète triplerait l'image pour un tableur
# et une base de données dont personne n'a besoin ici.
#
# C'est le premier paquet système de cette image, et le premier processus externe du
# backend. Si un jour le PDF est abandonné, ces lignes partent avec lui.
RUN apt-get update \n    && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-impress \n    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Couche dépendances (cache tant que pyproject/lock ne changent pas)
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Code applicatif
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
