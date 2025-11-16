#!/usr/bin/env bash
set -o errexit

# Обновление инструментов сборки
pip install --upgrade pip setuptools wheel

# Установка зависимостей
pip install -r requirements.txt

# Миграции
python manage.py migrate

# Сбор статических файлов
python manage.py collectstatic --noinput
