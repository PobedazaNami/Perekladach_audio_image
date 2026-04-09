# Telegram Translation Bot

## Деплой в режиме только текстового перевода (Mode 1)

### Описание
Бот настроен для работы только с текстовым переводом (Режим 1). 
Режимы 2 и 3 (обработка изображений и аудио) временно отключены для упрощения деплоя.

### Особенности текущей версии
- ✅ **Режим 1**: Перевод текста с немецкого на украинский с корректировкой артиклей
- ❌ **Режим 2**: Обработка изображений (временно отключена)
- ❌ **Режим 3**: Обработка аудио (временно отключена)
- ✅ **Режим 4**: Практические упражнения
- ✅ Кэширование (Memory + Redis + MongoDB)
- ✅ Сохранение переведенных слов
- ✅ Интернационализация (UK/RU/DE)

### Необходимые переменные окружения (.env)
```bash
# Основные (обязательные)
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
OPENAI_TRANSLATION_MODEL=gpt-4o
OPENAI_TRANSLATION_FALLBACK_MODEL=gpt-4o-mini
MONGODB_URI=your_mongodb_connection_string
ADMIN_IDS=662790795,other_admin_id

# Дополнительные
REDIS_URL=redis://localhost:6379/0
```

### Зависимости (requirements.txt)
Временно отключены Google Cloud и медиа-зависимости:
- google-cloud-vision
- google-cloud-speech  
- Pillow
- pydub

### Docker деплой
```bash
# Сборка образа
docker build -t translation_bot_app .

# Запуск с уникальными именами для избежания конфликтов
docker-compose -f docker-compose.prod.yml up -d
```

### GitHub Actions автодеплой
Настроен автоматический деплой при пуше в main ветку.

### Активация режимов 2-3 в будущем
1. Раскомментировать импорты Google Cloud в `bot.py`
2. Раскомментировать функции `handle_image`, `handle_audio`  
3. Раскомментировать зависимости в `requirements.txt`
4. Добавить `GOOGLE_APPLICATION_CREDENTIALS` в `.env`
5. Обновить `Dockerfile` для копирования credentials
