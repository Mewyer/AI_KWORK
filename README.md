VideoGenBot — это продвинутый Telegram-бот, предоставляющий пользователям следующие функции:

    Генерация видео из текста

    Поиск видеороликов

    Базовое редактирование видео

    Подписки и виртуальная валюта Stars

    Админ-панель со статистикой и управлением

🚀 Возможности

    /generate [текст] — генерация видео по текстовому описанию

    /search [ключевые слова] — поиск видео с Pexels

    /edit — отправьте видео с этой командой и получите отредактированную версию

    /subscription — информация о подписке, покупка подписок и Stars

    /admin — доступ к панели управления для администраторов

🛠 Установка

    Клонируйте репозиторий:
```bash
git clone https://github.com/yourname/videogenbot.git
cd videogenbot
```
Создайте виртуальное окружение и установите зависимости:

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

Создайте файл .env со следующими переменными:
``` bash
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321
PROVIDER_TOKEN=your_payment_provider_token
RUNWAY_API_KEY=your_runway_api_key
PEXELS_API_KEY=your_pexels_api_key
```
Убедитесь, что установлен ffmpeg:
```bash
ffmpeg -version
```
Запустите бота:
``` bash
    python bot.py
```
📦 Зависимости
``` bash
    python-telegram-bot

    python-dotenv

    requests

    sqlite3

    ffmpeg

    asyncio

    logging
```
💳 Подписки

Бот поддерживает 3 уровня подписки:
Тип	Лимит в день	Лимит в месяц	Цена (USD)	Длительность
Free	3	20	Бесплатно	Бессрочно
Pro	50	1500	$10	30 дней
Premium	200	6000	$30	30 дней

Также пользователи могут купить Stars — виртуальную валюту для дополнительных функций.
⚙️ Администрирование

Пользователи с ID, указанным в ADMIN_IDS, получают доступ к команде /admin с функциями:

    Просмотр статистики (активность, платежи)

    Просмотр пользователей

    Управление лимитами подписок

📁 Структура БД

    users — информация о пользователях, подписках и лимитах

    payments — история платежей

🧪 Примеры команд

/generate красивый закат на море
/search space exploration
/send_video с подписью /edit обрежь первые 5 секунд
/subscription
/admin

❗ Важно

    API ключи Pexels и Runway необходимы для корректной работы.

    Платежная система использует Telegram Payments с поддержкой Yookassa или Stripe.

    Видео обрабатываются локально с помощью ffmpeg.