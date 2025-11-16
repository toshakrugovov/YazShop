#!/usr/bin/env bash
set -o errexit

# Обновляем инструменты сборки
pip install --upgrade pip setuptools wheel

# Устанавливаем зависимости через готовые бинарные колеса
pip install --prefer-binary -r requirements.txt

# Применяем миграции
python manage.py migrate

# Собираем статические файлы
python manage.py collectstatic --noinput
