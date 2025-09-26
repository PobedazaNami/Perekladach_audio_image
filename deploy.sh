#!/bin/bash

# 🚀 Скрипт деплоя телеграм-бота

set -e

echo "🔄 Starting translation bot deployment..."

# Проверяем что мы в правильной директории
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ docker-compose.prod.yml not found! Make sure you're in the project directory."
    exit 1
fi

# Проверяем что .env файл существует
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Create it from .env.example"
    exit 1
fi

# Проверяем что credentials существуют
if [ ! -f "credentials/vision-api-key.json" ]; then
    echo "❌ Google Cloud credentials not found!"
    echo "Please upload vision-api-key.json to credentials/ folder"
    exit 1
fi

echo "✅ All required files found"

# Останавливаем старые контейнеры
echo "🛑 Stopping old containers..."
docker-compose -f docker-compose.prod.yml down || echo "No containers to stop"

# Собираем новые образы
echo "🔨 Building new images..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Запускаем контейнеры
echo "🚀 Starting containers..."
docker-compose -f docker-compose.prod.yml up -d

# Проверяем статус
echo "📊 Container status:"
docker-compose -f docker-compose.prod.yml ps

# Показываем логи
echo "📋 Recent logs:"
docker-compose -f docker-compose.prod.yml logs --tail=20

echo "✅ Translation bot deployed successfully!"
echo "📋 Use 'docker-compose -f docker-compose.prod.yml logs -f' to follow logs"