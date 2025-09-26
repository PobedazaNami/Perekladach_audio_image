# Используем официальный базовый образ Python
FROM python:3.10-slim

# Установим необходимые зависимости, включая ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Установим рабочую директорию
WORKDIR /app

# Копируем requirements.txt первым для кэширования слоев
COPY requirements.txt .

# Установим Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы проекта
COPY . /app

# Создаём директории для логов, если необходимо
RUN mkdir -p /app/logs

# Установим переменные окружения (можно переопределить при запуске)
ENV GOOGLE_APPLICATION_CREDENTIALS="credentials/vision-api-key.json"
ENV PYTHONUNBUFFERED=1

# Запустим бота
CMD ["python", "bot.py"]
