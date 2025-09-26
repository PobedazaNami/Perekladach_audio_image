# 🚀 ИНСТРУКЦИЯ ПО ДЕПЛОЮ ТЕЛЕГРАМ-БОТА

## 📋 ЧЕКЛИСТ ПЕРЕД ПУШЕМ В GITHUB

### ✅ 1. БЕЗОПАСНОСТЬ
- [x] `.env` файл в `.gitignore` 
- [x] `credentials/` папка в `.gitignore`
- [x] `.env.example` создан с примерами
- [ ] Проверить что в Git нет секретов: `git log --all --full-history -- .env`

### ✅ 2. ФАЙЛЫ ДЛЯ ДЕПЛОЯ
- [x] `Dockerfile` готов
- [x] `docker-compose.prod.yml` создан
- [x] `.github/workflows/deploy.yml` создан  
- [x] `requirements.txt` актуален
- [x] Лишние файлы удалены

## 🔧 НАСТРОЙКА GITHUB SECRETS

В GitHub репозитории добавьте Secrets:

```
HOST=your-server-ip
USERNAME=your-ssh-username  
SSH_PRIVATE_KEY=your-ssh-private-key
PORT=22
```

## 🖥️ НАСТРОЙКА СЕРВЕРА

### 1. Установка Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. Клонирование и настройка
```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
cp .env.example .env
nano .env  # Заполните реальными значениями
```

### 3. Создание credentials
```bash
mkdir credentials
# Загрузите vision-api-key.json в папку credentials/
```

### 4. Запуск
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 📊 МОНИТОРИНГ
```bash
# Логи бота
docker logs translation_bot -f

# Статус контейнеров  
docker ps

# Перезапуск
docker-compose -f docker-compose.prod.yml restart
```

## 🔄 АВТОДЕПЛОЙ
Настроен через GitHub Actions - коммиты в `main` автоматически деплоятся на сервер.

## ⚠️ ВАЖНЫЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
```bash
TELEGRAM_BOT_TOKEN=    # От @BotFather
OPENAI_API_KEY=       # От OpenAI
MONGODB_URI=          # MongoDB Atlas
REDIS_URL=            # redis://localhost:6379/0
ADMIN_IDS=            # ID админов через запятую
GOOGLE_APPLICATION_CREDENTIALS=credentials/vision-api-key.json
```