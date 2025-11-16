#!/usr/bin/env bash
set -o errexit

# Обновляем инструменты сборки, чтобы использовать готовые колеса
pip install --upgrade pip setuptools wheel

# Устанавливаем зависимости через бинарные колеса
pip install --prefer-binary -r requirements.txt

# Применяем миграции
python manage.py migrate

# Сбор статики
python manage.py collectstatic --noinput
