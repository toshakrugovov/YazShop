#!/usr/bin/env bash
set -o errexit

# Обновляем pip, setuptools и wheel
pip install --upgrade pip setuptools wheel

# Устанавливаем зависимости через готовые бинарные колеса
pip install --prefer-binary -r requirements.txt

# Миграции
python manage.py migrate

# Сбор статических файлов
python manage.py collectstatic --noinput
