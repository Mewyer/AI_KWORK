# Video Analysis Telegram Bot

## 📌 Описание проекта
Telegram бот для анализа видео с YouTube с помощью сервиса videohunt.ai. Основные функции:
- Анализ видео по пользовательскому запросу
- Гибкая система подписок с лимитами запросов
- Автоматическое создание скриншотов результатов
- Административная панель управления

## 🛠 Технологии
```python
# Основные зависимости
requirements = [
    "python-telegram-bot==20.3",
    "selenium==4.9.0",
    "Pillow==10.0.0",
    "python-dotenv==1.0.0"
]
```
## ⚙️ Установка
``` bash 
# 1. Клонировать репозиторий
git clone https://github.com/Mewyer/AI_KWORK
cd AI_KWORK

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Установить ChromeDriver (пример для Windows)
choco install chromedriver
```

## 🔧 Конфигурация
```bash 
# .env файл
TELEGRAM_TOKEN="ваш_токен_бота"
PAYMENT_PROVIDER_TOKEN="ваш_токен_оплаты"  # опционально
DB_NAME="bot_database.db"
NEW_SCRIPT_PATH="new.py"
```

## 🚀 Запуск
```bash
# Основной бот
python main.py

# Для тестирования обработки видео
python new.py "https://youtube.com/watch?v=..." "Ваш промт" "screenshot.png"
```

## 🤖 Команды бота
```bash
commands = (
    "/start": "Начало работы",
    "/video": "Анализ видео (пошаговый ввод)",
    "/buy": "Купить подписку",
    "/admin": "Админ-панель (только для админов)"
)
```

## 🗃 Структура БД
```bash 
-- Основные таблицы
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    registration_date TEXT,
    is_admin INTEGER DEFAULT 0
);

CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    subscription_type TEXT,
    start_date TEXT,
    end_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
```

## 🔄 Workflow анализа видео

sequenceDiagram
    User->>Bot: /video
    Bot->>User: "Отправьте ссылку на видео"
    User->>Bot: YouTube ссылка
    Bot->>User: "Отправьте промт для анализа"
    User->>Bot: Текст промта
    Bot->>Worker: Запуск обработки
    Worker->>Bot: Результаты анализа
    Bot->>User: Скриншоты + данные

## 🚨 Возможные проблемы
```python
common_issues = {
    "SSL_ERRORS": "Добавьте в ChromeOptions: --ignore-certificate-errors",
    "SCREENSHOTS_FAIL": "1. Проверьте права\n2. Убедитесь в наличии Pillow",
    "BOT_NOT_RESPONDING": "Проверьте асинхронные обработчики"
}
```