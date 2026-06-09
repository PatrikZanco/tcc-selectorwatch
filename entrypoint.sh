#!/bin/bash
set -e

echo "→ Gerando migrations..."
python manage.py makemigrations monitor --no-input

echo "→ Aplicando migrations..."
python manage.py migrate --no-input

echo "→ Iniciando: $@"
exec "$@"
