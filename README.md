# Video Analysis Telegram Bot

## 📌 Описание проекта
Telegram бот для анализа видео с YouTube с помощью сервиса videohunt.ai. Основные функции:
- Анализ видео по пользовательскому запросу
- Гибкая система подписок (бесплатная и премиум) с лимитами запросов
- Интеграция с платежной системой Telegram
- Автоматическая авторизация на videohunt.ai через Selenium
- Полноценная админ-панель с управлением настройками
- Возможность изменения пароля аккаунта videohunt.ai через бота

## 🛠 Технологии
- Python 3.10+
- Telegram Bot API
- Selenium для автоматизации браузера
- SQLite для хранения данных
- ChromeDriver для работы с браузером

## ⚙️ Установка
```bash
# 1. Клонировать репозиторий
git clone https://github.com/Mewyer/AI_KWORK
cd AI_KWORK

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Установить ChromeDriver (пример для Windows)
choco install chromedriver
# Или скачать вручную: https://chromedriver.chromium.org/downloads

```

## 🔧 Конфигурация
Создайте файл .env со следующими параметрами:
```bash 
TELEGRAM_TOKEN="ваш_токен_бота"
ADMIN_IDS="6107527766"  # ID администраторов через запятую
PAYMENT_PROVIDER_TOKEN="ваш_токен_оплаты"  # для платежей
CHROME_DRIVER_PATH="путь_к_chromedriver"
ACCOUNT_EMAIL="email_для_videohunt.ai"
ACCOUNT_PASSWORD="пароль_для_videohunt.ai"
DB_NAME="bot_database.db"
```

## 🚀 Запуск
```bash
python bot.py
```

## 🤖 Команды бота
# Основные команды:
- /start - Начало работы с ботом
- /video - Анализ видео (пошаговый ввод)
- /buy - Купить премиум подписку

# Админ-команды (только для администраторов):
- /admin - Панель администратора
- /stats - Статистика бота
- /set_free_requests - Изменить лимит запросов для бесплатной подписки
- /set_premium_requests - Изменить лимит запросов для премиум подписки
- /set_price - Изменить цену подписки
- /broadcast - Сделать рассылку всем пользователям
- /change_videohunt_password - Изменить пароль аккаунта videohunt.ai