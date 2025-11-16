#!/usr/bin/env bash
set -o errexit

# Установка зависимостей
pip install -r requirements.txt

# Миграции
python manage.py migrate

# Сбор статических файлов
python manage.py collectstatic --noinput
