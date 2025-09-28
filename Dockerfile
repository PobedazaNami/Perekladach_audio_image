# Используем официальный базовый образ Python
FROM python:3.10-slim

# Временно убираем ffmpeg для режима только текстового перевода
# RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Установим рабочую директорию
WORKDIR /app

# Копируем requirements.txt первым для кэширования слоев
COPY requirements.txt .

# Установим Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы проекта (кроме credentials для режима только текстового перевода)
COPY bot.py config.py database.py models.py high_performance_api.py performance_cache.py smart_ux.py translations.py ./

# Создаём директории для логов, если необходимо
RUN mkdir -p /app/logs

# Установим переменные окружения (Google credentials временно не нужны)
# ENV GOOGLE_APPLICATION_CREDENTIALS="credentials/vision-api-key.json"
ENV PYTHONUNBUFFERED=1

# Запустим бота
CMD ["python", "bot.py"]
