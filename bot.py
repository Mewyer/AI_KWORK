import logging
import sqlite3
import asyncio
import urllib.parse
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    PreCheckoutQueryHandler
)

# Настройки логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv()
ADMIN_IDS = [] 
DB_NAME = 'bot_database.db'
PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN')
NEW_SCRIPT_PATH = 'new.py'  # Путь к скрипту new.py

SUBSCRIPTION_TYPES = {
    'free': {
        'name': 'Бесплатная',
        'price': 0,
        'currency': 'XTR',
        'daily_requests': None  
    },
    'premium': {
        'name': 'Премиум',
        'price': 100,
        'currency': 'XTR',
        'daily_requests': None 
    }
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        registration_date TEXT,
        is_admin INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subscription_type TEXT,
        start_date TEXT,
        end_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        request_date TEXT,
        request_type TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        free_daily_requests INTEGER DEFAULT 5,
        premium_daily_requests INTEGER DEFAULT 15,
        subscription_price INTEGER DEFAULT 100
    )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO settings (
            free_daily_requests, 
            premium_daily_requests, 
            subscription_price
        ) VALUES (?, ?, ?)
        ''', (5, 15, 100))
    
    conn.commit()
    conn.close()
    
    load_settings_to_subscription_types()

def load_settings_to_subscription_types():
    """Загружает настройки из базы в SUBSCRIPTION_TYPES"""
    settings = get_settings()
    if settings:
        SUBSCRIPTION_TYPES['free']['daily_requests'] = settings['free_daily_requests']
        SUBSCRIPTION_TYPES['premium']['daily_requests'] = settings['premium_daily_requests']

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def register_user(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, registration_date)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, datetime.now().isoformat()))
    

    cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE user_id = ?', (user_id,))
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO subscriptions (user_id, subscription_type, start_date, end_date)
        VALUES (?, ?, ?, ?)
        ''', (
            user_id, 
            'free', 
            datetime.now().isoformat(), 
            (datetime.now() + timedelta(days=365)).isoformat()
        ))
    
    conn.commit()
    conn.close()

def get_user_subscription(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT s.subscription_type, s.start_date, s.end_date
    FROM subscriptions s
    WHERE s.user_id = ? AND s.end_date > ?
    ORDER BY s.end_date DESC
    LIMIT 1
    ''', (user_id, datetime.now().isoformat()))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        subscription_type, start_date, end_date = result
        return {
            'type': subscription_type,
            'name': SUBSCRIPTION_TYPES[subscription_type]['name'],
            'start_date': datetime.fromisoformat(start_date),
            'end_date': datetime.fromisoformat(end_date)
        }
    return None

def get_today_requests_count(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().date().isoformat()
    cursor.execute('''
    SELECT COUNT(*) 
    FROM requests 
    WHERE user_id = ? AND date(request_date) = ?
    ''', (user_id, today))
    
    count = cursor.fetchone()[0]
    conn.close()
    return count

def log_request(user_id, request_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO requests (user_id, request_date, request_type)
    VALUES (?, ?, ?)
    ''', (user_id, datetime.now().isoformat(), request_type))
    
    conn.commit()
    conn.close()

def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        free_daily_requests, 
        premium_daily_requests, 
        subscription_price 
    FROM settings 
    LIMIT 1
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'free_daily_requests': result[0],
            'premium_daily_requests': result[1],
            'subscription_price': result[2]
        }
    return None

def update_settings(free_daily=None, premium_daily=None, price=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current = get_settings()
    if not current:
        conn.close()
        return False
    
    if free_daily is None:
        free_daily = current['free_daily_requests']
    if premium_daily is None:
        premium_daily = current['premium_daily_requests']
    if price is None:
        price = current['subscription_price']
    
    try:
        cursor.execute('''
        UPDATE settings
        SET 
            free_daily_requests = ?,
            premium_daily_requests = ?,
            subscription_price = ?
        ''', (free_daily, premium_daily, price))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек: {str(e)}")
        return False
    finally:
        conn.close()

def get_bot_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT COUNT(DISTINCT user_id) 
    FROM subscriptions 
    WHERE subscription_type = 'premium' AND end_date > ?
    ''', (datetime.now().isoformat(),))
    premium_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM requests')
    total_requests = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'premium_users': premium_users,
        'total_requests': total_requests
    }

async def start(update: Update, context: CallbackContext) -> None:
    """Отправляет приветственное сообщение"""
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
    
    settings = get_settings()
    subscription = get_user_subscription(user.id)
    
    text = (
        f"Привет, {user.first_name}! Я бот для анализа видео\n\n"
        f"Ваша подписка: {subscription['name']}\n"
        f"Лимиты:\n"
        f"- Запросов в день: {settings['free_daily_requests'] if subscription['type'] == 'free' else settings['premium_daily_requests']}\n"
        "Доступные команды:\n"
        "/video [ссылка] [промт] - Анализ видео\n"
        "/buy - Купить подписку\n"
    )
    
    if user.id in ADMIN_IDS:
        text += "\n\nАдмин-команды:\n/admin - Панель администратора"
    
    await update.message.reply_text(text)

async def video_command(update: Update, context: CallbackContext) -> None:
    """Обрабатывает команду /video с пошаговым вводом"""
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
    
    subscription = get_user_subscription(user.id)
    settings = get_settings()
    daily_requests = get_today_requests_count(user.id)
    
    max_requests = settings['free_daily_requests'] if subscription['type'] == 'free' else settings['premium_daily_requests']
    
    if daily_requests >= max_requests:
        await update.message.reply_text(
            f"❌ Вы исчерпали дневной лимит запросов ({max_requests}).\n"
            "Используйте /buy для покупки подписки."
        )
        return
    
    context.user_data['awaiting_video_url'] = True
    await update.message.reply_text(
        "Отправьте ссылку на YouTube видео для анализа:"
    )


async def send_results(update: Update, result_url: str):
    """Отправляет результаты пользователю"""
    try:
        keyboard = [[InlineKeyboardButton("🔗 Открыть результаты", url=result_url)]]
        await update.message.reply_text(
            "Ссылка с результатами анализа готова!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке результатов: {str(e)}")
        await update.message.reply_text(f"Вот ваша ссылка с результатами:\n{result_url}")

async def buy_subscription(update: Update, context: CallbackContext):
    """Показывает информацию о покупке подписки"""
    user = update.effective_user
    settings = get_settings()
    
    price = settings['subscription_price']

    title = "Премиум подписка"
    description = (
        f"Доступно {settings['premium_daily_requests']} запросов в день\n"
        "Без ограничений на количество запросов"
    )
    payload = f"subscription_{user.id}"
    currency = "XTR"
    prices = [LabeledPrice("Премиум подписка", price)]
    
    await context.bot.send_invoice(
        chat_id=user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency=currency,
        prices=prices,
        start_parameter="premium_subscription",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )

async def precheckout_callback(update: Update, context: CallbackContext):
    """Обрабатывает предварительный запрос на оплату"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: CallbackContext):
    """Обрабатывает успешную оплату"""
    user = update.effective_user
    payment = update.message.successful_payment
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    end_date = datetime.now() + timedelta(days=30)
    cursor.execute('''
    INSERT INTO subscriptions (user_id, subscription_type, start_date, end_date)
    VALUES (?, ?, ?, ?)
    ''', (user.id, 'premium', datetime.now().isoformat(), end_date.isoformat()))
    
    conn.commit()
    conn.close()
    
    settings = get_settings()
    
    await update.message.reply_text(
        f"✅ Оплата прошла успешно! Вы получили премиум подписку.\n"
        f"Теперь у вас {settings['premium_daily_requests']} запросов в день.\n"
        f"Подписка активна до {end_date.strftime('%d.%m.%Y')}"
    )

async def process_video_async(update: Update, context: CallbackContext, video_url: str, prompt: str):
    """Асинхронная обработка видео"""
    try:
        # Создаем временные файлы
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            screenshot_path = tmp_file.name
        
        # Запускаем new.py в отдельном процессе
        process = await asyncio.create_subprocess_exec(
            'python', 
            NEW_SCRIPT_PATH, 
            video_url, 
            prompt,
            screenshot_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Ждем завершения процесса
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Ошибка выполнения new.py: {stderr.decode()}")
            await update.message.reply_text("❌ Произошла ошибка при обработке видео")
            return
        
        # Отправляем основной скриншот
        if os.path.exists(screenshot_path):
            with open(screenshot_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=InputFile(photo),
                    caption="Результат анализа видео"
                )
        else:
            await update.message.reply_text("⚠️ Не удалось создать основной скриншот")
        
        # Отправляем скриншоты элементов
        screenshots_dir = os.path.join(os.path.dirname(screenshot_path), "screenshots")
        if os.path.exists(screenshots_dir):
            screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
            if not screenshots:
                await update.message.reply_text("⚠️ Не найдены скриншоты элементов")
            else:
                for screenshot_file in sorted(screenshots):
                    file_path = os.path.join(screenshots_dir, screenshot_file)
                    try:
                        with open(file_path, 'rb') as photo:
                            await update.message.reply_photo(
                                photo=InputFile(photo),
                                caption=f"Фрагмент {screenshot_file.replace('.png', '')}"
                            )
                    except Exception as e:
                        logger.error(f"Ошибка отправки {file_path}: {str(e)}")
        
        log_request(user.id, 'video_analysis')
        
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при обработке видео")
    finally:
        # Удаляем временные файлы
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        
        screenshots_dir = os.path.join(os.path.dirname(screenshot_path), "screenshots")
        if os.path.exists(screenshots_dir):
            for screenshot_file in os.listdir(screenshots_dir):
                if screenshot_file.endswith('.png'):
                    os.remove(os.path.join(screenshots_dir, screenshot_file))
            os.rmdir(screenshots_dir)

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Обрабатывает сообщения пользователя"""
    user = update.effective_user
    text = update.message.text.strip()
    
    if context.user_data.get('awaiting_video_url'):
        if is_valid_url(text):
            clean_url = clean_video_url(text)
            if 'youtube.com' in clean_url or 'youtu.be' in clean_url:
                context.user_data['video_url'] = clean_url
                context.user_data['awaiting_video_url'] = False
                context.user_data['awaiting_prompt'] = True
                await update.message.reply_text("✅ Ссылка принята. Теперь отправьте промт для анализа:")
            else:
                await update.message.reply_text("❌ Пожалуйста, отправьте ссылку на YouTube.")
        else:
            await update.message.reply_text("❌ Некорректная ссылка. Попробуйте еще раз.")
    
    elif context.user_data.get('awaiting_prompt'):
        prompt = text
        video_url = context.user_data['video_url']
        
        await update.message.reply_text("🔄 Начинаю обработку видео. Вы можете продолжать использовать другие команды...")
        
        # Запускаем обработку видео в фоне
        asyncio.create_task(process_video_async(update, context, video_url, prompt))
        
        # Очищаем контекст
        if 'video_url' in context.user_data:
            del context.user_data['video_url']
        if 'awaiting_prompt' in context.user_data:
            del context.user_data['awaiting_prompt']
    
    # Обработка других команд и сообщений
    elif text.startswith('/'):
        await update.message.reply_text("Пожалуйста, используйте команды через меню или дождитесь завершения текущей задачи.")
        

async def admin_panel(update: Update, context: CallbackContext):
    """Показывает панель администратора"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    text = (
        "Админ-панель:\n\n"
        "Доступные команды:\n"
        "/stats - Статистика бота\n"
        "/set_free_requests - Изменить лимит запросов для бесплатной подписки\n"
        "/set_premium_requests - Изменить лимит запросов для премиум подписки\n"
        "/set_price - Изменить цену подписки\n"
        "/broadcast - Сделать рассылку\n"
    )
    
    await update.message.reply_text(text)

async def admin_stats(update: Update, context: CallbackContext):
    """Показывает статистику бота"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    stats = get_bot_stats()
    settings = get_settings()
    
    text = (
        "📊 Статистика бота:\n\n"
        f"Количество пользователей: {stats['total_users']}\n"
        f"Пользователей с активной подпиской: {stats['premium_users']}\n"
        f"Всего запросов: {stats['total_requests']}\n\n"
        "Текущие настройки:\n"
        f"- Цена подписки: {settings['subscription_price'] / 100:.2f} {SUBSCRIPTION_TYPES['premium']['currency']}\n"
        f"- Запросов/день (без подписки): {settings['free_daily_requests']}\n"
        f"- Запросов/день (с подпиской): {settings['premium_daily_requests']}\n"
    )
    
    await update.message.reply_text(text)

async def set_free_requests(update: Update, context: CallbackContext):
    """Установка лимита запросов для бесплатной подписки"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text("Используйте: /set_free_requests <количество>")
        return
    
    try:
        value = int(context.args[0])
        if value < 1:
            raise ValueError("Количество запросов должно быть не менее 1")
        
        if update_settings(free_daily=value):
            SUBSCRIPTION_TYPES['free']['daily_requests'] = value
            response = f"✅ Лимит запросов/день (без подписки) изменен на {value}"
        else:
            raise ValueError("Ошибка при обновлении базы данных")
        
        await update.message.reply_text(response)
    
    except ValueError as e:
        error_msg = f"❌ Ошибка: {str(e)}\nПожалуйста, введите корректное число."
        await update.message.reply_text(error_msg)

async def set_premium_requests(update: Update, context: CallbackContext):
    """Установка лимита запросов для премиум подписки"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text("Используйте: /set_premium_requests <количество>")
        return
    
    try:
        value = int(context.args[0])
        if value < 1:
            raise ValueError("Количество запросов должно быть не менее 1")
        
        if update_settings(premium_daily=value):
            SUBSCRIPTION_TYPES['premium']['daily_requests'] = value
            response = f"✅ Лимит запросов/день (с подпиской) изменен на {value}"
        else:
            raise ValueError("Ошибка при обновлении базы данных")
        
        await update.message.reply_text(response)
    
    except ValueError as e:
        error_msg = f"❌ Ошибка: {str(e)}\nПожалуйста, введите корректное число."
        await update.message.reply_text(error_msg)

async def set_price(update: Update, context: CallbackContext):
    """Установка цены подписки"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text(f"Используйте: /set_price <цена в {SUBSCRIPTION_TYPES['premium']['currency']}>")
        return
    
    try:
        value = int(float(context.args[0]) * 100)
        if value <= 0:
            raise ValueError("Цена должна быть больше 0")
        
        if update_settings(price=value):
            SUBSCRIPTION_TYPES['premium']['price'] = value
            response = f"✅ Цена подписки изменена на {value / 100:.2f} {SUBSCRIPTION_TYPES['premium']['currency']}"
        else:
            raise ValueError("Ошибка при обновлении базы данных")
        
        await update.message.reply_text(response)
    
    except ValueError as e:
        error_msg = f"❌ Ошибка: {str(e)}\nПожалуйста, введите корректное число."
        await update.message.reply_text(error_msg)

async def broadcast(update: Update, context: CallbackContext):
    """Рассылка сообщения всем пользователям"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text("Используйте: /broadcast <сообщение>")
        return
    
    message = ' '.join(context.args)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 Сообщение от администратора:\n\n{message}"
            )
            success += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {str(e)}")
            failed += 1
    
    await update.message.reply_text(
        f"✅ Рассылка завершена:\n"
        f"Успешно отправлено: {success}\n"
        f"Не удалось отправить: {failed}"
    )
            
def is_valid_url(url: str) -> bool:
    """Проверяет валидность URL"""
    parsed = urllib.parse.urlparse(url)
    return all([parsed.scheme, parsed.netloc])

def clean_video_url(url: str) -> str:
    """Очищает URL видео от ненужных параметров"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return url.split('&')[0]
    return url


def main() -> None:
    """Запуск бота"""
    init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("video", video_command))
    application.add_handler(CommandHandler("buy", buy_subscription))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("set_free_requests", set_free_requests))
    application.add_handler(CommandHandler("set_premium_requests", set_premium_requests))
    application.add_handler(CommandHandler("set_price", set_price))
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()