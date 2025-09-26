# 🚀 ИНСТРУКЦИЯ ПО ДЕПЛОЮ ТЕЛЕГРАМ-БОТА (МУЛЬТИПРОЕКТНЫЙ СЕРВЕР)

## 📋 ОСОБЕННОСТИ ДЛЯ СЕРВЕРА С НЕСКОЛЬКИМИ ПРОЕКТАМИ

### ✅ ИЗБЕГАЕМ КОНФЛИКТОВ:
- **Порты**: Redis на порту 6380 (не 6379)
- **Имена контейнеров**: `translation_bot_app`, `translation_redis_cache`
- **Сети**: `translation_network`
- **Volumes**: `translation_redis_data`
- **Директория**: `/opt/translation-bot` (отдельная папка)

## �️ НАСТРОЙКА СЕРВЕРА (С ДРУГИМИ ПРОЕКТАМИ)

### 1. Клонирование в отдельную папку
```bash
# Создаем отдельную директорию для проекта
sudo mkdir -p /opt/translation-bot
cd /opt/translation-bot

# Клонируем проект
git clone https://github.com/PobedazaNami/Perekladach_audio_image.git .

# Устанавливаем права
sudo chown -R $USER:$USER /opt/translation-bot
```

### 2. Настройка окружения
```bash
# Копируем и настраиваем .env
cp .env.example .env
nano .env  # Заполните реальными значениями

# Создаем директории
mkdir -p credentials logs

# Загружаем Google Cloud ключи
# Скопируйте vision-api-key.json в папку credentials/
```

### 3. Варианты запуска

#### Вариант 1: С собственным Redis (рекомендуется)
```bash
# Использует порт 6380 для Redis
docker-compose -f docker-compose.prod.yml up -d
```

#### Вариант 2: С существующим Redis на сервере
```bash
# В .env укажите REDIS_URL=redis://localhost:6379/1
# Где 1 - номер базы данных (чтобы не мешать другим проектам)
docker-compose -f docker-compose.external-redis.yml up -d
```

#### Вариант 3: Быстрый деплой скриптом
```bash
chmod +x deploy.sh
./deploy.sh
```

## 📊 МОНИТОРИНГ

### Проверка статуса
```bash
# Статус контейнеров
docker ps | grep translation

# Логи бота
docker logs translation_bot_app -f

# Логи Redis
docker logs translation_redis_cache -f

# Общие логи
docker-compose -f docker-compose.prod.yml logs -f
```

### Проверка портов (чтобы избежать конфликтов)
```bash
# Посмотреть занятые порты
netstat -tulpn | grep :6380
netstat -tulpn | grep :6379

# Список всех Docker контейнеров
docker ps -a
```

## 🔄 УПРАВЛЕНИЕ

### Остановка/запуск
```bash
# Остановить
docker-compose -f docker-compose.prod.yml down

# Запустить
docker-compose -f docker-compose.prod.yml up -d

# Перезапуск
docker-compose -f docker-compose.prod.yml restart
```

### Обновление
```bash
cd /opt/translation-bot
git pull origin main
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

## ⚠️ ВАЖНЫЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
```bash
TELEGRAM_BOT_TOKEN=    # От @BotFather
OPENAI_API_KEY=       # От OpenAI
MONGODB_URI=          # MongoDB Atlas
REDIS_URL=            # redis://translation_redis:6379/0 (для собственного Redis)
                      # redis://localhost:6379/1 (для внешнего Redis)
ADMIN_IDS=            # ID админов через запятую
GOOGLE_APPLICATION_CREDENTIALS=credentials/vision-api-key.json
```

## 🐳 СТРУКТУРА КОНТЕЙНЕРОВ
```
translation_bot_app      -> Основное приложение бота
translation_redis_cache  -> Redis кэш (порт 6380)
translation_network      -> Изолированная сеть проекта
```