# Python образ
FROM python:3.11-slim

# Системные зависимости (для uvicorn и т.п.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем зависимости и ставим их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Открываем порт для платформы
EXPOSE 8080

# ВАЖНО: запускаем uvicorn, чтобы FastAPI не завершался
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
