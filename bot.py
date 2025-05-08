import os
import sqlite3
import logging
import requests
import asyncio
import random
import tempfile
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    PreCheckoutQueryHandler,
    ConversationHandler
)

# Загрузка конфигурации
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Настройки подписок
SUBSCRIPTION_PLANS = {
    "free": {"daily_limit": 3, "monthly_limit": 20},
    "pro": {"daily_limit": 50, "monthly_limit": 1500, "price": 1000, "duration": 30},
    "premium": {"daily_limit": 200, "monthly_limit": 6000, "price": 3000, "duration": 30}
}

# Состояния для ConversationHandler
SET_LIMITS, SET_PRICE = range(2)

# Инициализация логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        join_date TEXT,
        subscription TEXT DEFAULT 'free',
        expiry_date TEXT,
        daily_used INTEGER DEFAULT 0,
        monthly_used INTEGER DEFAULT 0,
        last_used_date TEXT,
        stars_balance INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        currency TEXT,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

class Database:
    @staticmethod
    def get_user(user_id: int):
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user

    @staticmethod
    def update_user(user_id: int, **kwargs):
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
    
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
    
        if not exists:
            columns = ['user_id'] + list(kwargs.keys())
            placeholders = ['?'] * len(columns)
            values = [user_id] + list(kwargs.values())
        
            cursor.execute(f'''
            INSERT INTO users ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            ''', values)
        else:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values())
            values.append(user_id)
            
            cursor.execute(f'''
            UPDATE users SET {set_clause} WHERE user_id = ?
            ''', values)
    
        conn.commit()
        conn.close()

    @staticmethod
    def add_payment(user_id: int, payment_id: str, amount: int, currency: str):
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO payments (payment_id, user_id, amount, currency, date)
        VALUES (?, ?, ?, ?, ?)
        ''', (payment_id, user_id, amount, currency, datetime.now().strftime("%Y-%m-%d")))
        
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_users():
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, subscription, expiry_date FROM users')
        users = cursor.fetchall()
        conn.close()
        return users

    @staticmethod
    def get_payment_stats():
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute('''
        SELECT COUNT(*), SUM(amount) FROM payments 
        WHERE date >= date('now', '-30 days')
        ''')
        stats = cursor.fetchone()
        conn.close()
        return stats

class SubscriptionManager:
    @staticmethod
    def check_limits(user_id: int):
        user = Database.get_user(user_id)
        if not user:
            return False
            
        today = datetime.now().strftime("%Y-%m-%d")
        sub_plan = SUBSCRIPTION_PLANS.get(user[4], SUBSCRIPTION_PLANS['free'])
        
        if user[8] != today:
            Database.update_user(user_id, daily_used=0, last_used_date=today)
            user = (user[0], user[1], user[2], user[3], user[4], user[5], 0, user[7], today, user[9])
        
        if (user[6] >= sub_plan['daily_limit'] or 
            user[7] >= sub_plan['monthly_limit']):
            return False
            
        return True

    @staticmethod
    def increment_usage(user_id: int):
        Database.update_user(
            user_id,
            daily_used=sqlite3.connect('bot.db').execute(
                'SELECT daily_used + 1 FROM users WHERE user_id = ?', 
                (user_id,)
            ).fetchone()[0],
            monthly_used=sqlite3.connect('bot.db').execute(
                'SELECT monthly_used + 1 FROM users WHERE user_id = ?', 
                (user_id,)
            ).fetchone()[0]
        )

class VideoTools:
    @staticmethod
    async def download_video(video_url: str, output_path: str):
        """Скачивание видео по URL"""
        try:
            response = requests.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Video download failed: {str(e)}")
            return False

    @staticmethod
    async def generate_video_from_text(prompt: str):
        """Генерация видео из текста"""
        if not prompt or len(prompt.strip()) < 5:
            logger.error("Prompt is too short or empty")
            return None

        url = "https://api.runwayml.com/v1/text-to-video/generate"
        headers = {
            "Authorization": f"Bearer {RUNWAY_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        data = {
            "text_prompt": prompt[:200],
            "seed": random.randint(0, 10000),
            "cfg_scale": 7.5,
            "motion_bucket_id": 40,
            "width": 512,
            "height": 512,
            "fps": 12,
            "duration_seconds": 4
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            result = response.json()
            return result.get("output_url")
        except Exception as e:
            logger.error(f"Video generation failed: {str(e)}")
            return None

    @staticmethod
    async def search_videos(query: str):
        """Поиск видео"""
        if not query or len(query.strip()) < 2:
            return []

        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": 3,
            "size": "small",
            "orientation": "landscape"
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for video in data.get("videos", [])[:3]:
                if video.get("video_files"):
                    best_file = min(
                        (f for f in video["video_files"] if f.get("quality") == "sd"),
                        key=lambda x: x.get("width", 0)
                    )
                    videos.append(best_file["link"])
            return videos
        except Exception as e:
            logger.error(f"Video search failed: {str(e)}")
            return []

# Основные команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not Database.get_user(user.id):
        Database.update_user(
            user.id,
            username=user.username,
            full_name=user.full_name,
            join_date=datetime.now().strftime("%Y-%m-%d"),
            subscription="free"
        )
    
    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "🎥 Я - продвинутый видео-бот с функциями:\n"
        "• Генерация видео из текста /generate\n"
        "• Поиск видео /search\n"
        "• Автомонтаж /edit\n"
        "• Подписки /subscription"
    )
    
    if user.id in ADMIN_IDS:
        text += "\n\n🛠 Доступно: /admin - Панель управления"
    
    await update.message.reply_text(text)

async def show_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = Database.get_user(user_id)
    
    if not user:
        Database.update_user(
            user_id,
            username=update.effective_user.username,
            full_name=update.effective_user.full_name,
            join_date=datetime.now().strftime("%Y-%m-%d"),
            subscription="free"
        )
        user = Database.get_user(user_id)
        if not user:
            await update.message.reply_text("❌ Ошибка при создании вашего профиля.")
            return
    
    sub_plan = SUBSCRIPTION_PLANS.get(user[4], SUBSCRIPTION_PLANS['free'])
    expiry = f"\n🔚 Истекает: {user[5]}" if user[5] else ""
    
    text = (
        f"📌 Ваша подписка: {user[4].upper()}{expiry}\n"
        f"📊 Использовано: {user[6]}/{sub_plan['daily_limit']} (день), "
        f"{user[7]}/{sub_plan['monthly_limit']} (месяц)\n"
        f"🌟 Stars: {user[9]}"
    )
    
    keyboard = []
    if user[4] == 'free':
        keyboard.append([InlineKeyboardButton("💎 Оформить PRO", callback_data="upgrade_pro")])
        keyboard.append([InlineKeyboardButton("🚀 Оформить PREMIUM", callback_data="upgrade_premium")])
    else:
        keyboard.append([InlineKeyboardButton("🔄 Продлить подписку", callback_data=f"upgrade_{user[4]}")])
    
    keyboard.append([InlineKeyboardButton("⭐ Купить Stars", callback_data="buy_stars")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
)

async def generate_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not SubscriptionManager.check_limits(user_id):
        await update.message.reply_text("❌ Лимит запросов исчерпан! Используйте /subscription")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: /generate [описание видео]")
        return
    
    await update.message.reply_text("🔄 Генерирую видео...")
    
    if video_url := await VideoTools.generate_video_from_text(" ".join(context.args)):
        SubscriptionManager.increment_usage(user_id)
        await update.message.reply_video(video=video_url)
    else:
        await update.message.reply_text("❌ Ошибка генерации видео")

async def search_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not SubscriptionManager.check_limits(user_id):
        await update.message.reply_text("❌ Лимит запросов исчерпан! Используйте /subscription")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: /search [запрос]")
        return
    
    await update.message.reply_text("🔍 Ищу видео...")
    
    if videos := await VideoTools.search_videos(" ".join(context.args)):
        SubscriptionManager.increment_usage(user_id)
        for video_url in videos[:3]:
            await update.message.reply_video(video=video_url)
    else:
        await update.message.reply_text("❌ Видео не найдены")

async def edit_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not SubscriptionManager.check_limits(user_id):
        await update.message.reply_text("❌ Лимит запросов исчерпан! Используйте /subscription")
        return
    
    if not update.message.video and not update.message.document:
        await update.message.reply_text(
            "ℹ️ Отправьте видео файлом с подписью /edit [промт]\n\n"
            "Примеры промтов:\n"
            "• \"Обрежь первые 10 секунд\"\n"
            "• \"Добавить фильтр noir\"\n"
            "• \"Ускорить в 1.5x\""
        )
        return
    
    try:
        msg = await update.message.reply_text("🔄 Начинаю обработку видео...")
        
        # Получаем видео
        video_file = await context.bot.get_file(update.message.video or update.message.document)
        temp_input = f"input_{user_id}.mp4"
        await video_file.download_to_drive(temp_input)
        
        # Создаем временный выходной файл
        temp_output = f"output_{user_id}.mp4"
        
        # Простая обработка с помощью ffmpeg (пример)
        command = [
            'ffmpeg',
            '-i', temp_input,
            '-vf', 'scale=640:-1',  # Изменение размера
            '-c:a', 'copy',
            '-y', temp_output
        ]
        subprocess.run(command, check=True)
        
        # Отправляем результат
        with open(temp_output, 'rb') as result_file:
            await update.message.reply_video(
                video=result_file,
                caption="✅ Видео обработано",
                supports_streaming=True
            )
        
        await msg.delete()
        SubscriptionManager.increment_usage(user_id)
        
    except Exception as e:
        logger.error(f"Editing failed: {str(e)}")
        await update.message.reply_text("❌ Ошибка при обработке видео")
    finally:
        # Удаляем временные файлы
        for f in [temp_input, temp_output]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

# Платежи и подписки
async def upgrade_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sub_type = query.data.split('_')[1]
    plan = SUBSCRIPTION_PLANS.get(sub_type)
    
    if not plan:
        await query.answer("Неизвестный тип подписки")
        return
    
    await query.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"{sub_type.upper()} подписка",
        description=f"Доступ на {plan['duration']} дней",
        payload=f"sub_{sub_type}",
        provider_token=PROVIDER_TOKEN,
        currency="USD",
        prices=[LabeledPrice(f"{sub_type.upper()} подписка", plan['price'] * 100)]
    )

async def buy_stars_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("⭐ 100 Stars ($1)", callback_data="stars_100")],
        [InlineKeyboardButton("🌟 500 Stars ($5)", callback_data="stars_500")],
        [InlineKeyboardButton("💫 1000 Stars ($10)", callback_data="stars_1000")]
    ]
    
    await query.edit_message_text(
        "Выберите количество Stars для покупки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
)

async def process_stars_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    amount = int(query.data.split('_')[1])
    
    await query.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"Покупка {amount} Stars",
        description="Пополнение баланса Telegram Stars",
        payload=f"stars_{amount}",
        provider_token=PROVIDER_TOKEN,
        currency="USD",
        prices=[LabeledPrice(f"{amount} Stars", amount * 100)]
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload.startswith(('sub_', 'stars_')):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Ошибка платежа")

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    
    Database.add_payment(
        user_id,
        payment.invoice_payload,
        payment.total_amount // 100,
        payment.currency
    )
    
    if payment.invoice_payload.startswith('sub_'):
        sub_type = payment.invoice_payload.split('_')[1]
        expiry = (datetime.now() + timedelta(days=SUBSCRIPTION_PLANS[sub_type]['duration'])).strftime("%Y-%m-%d")
        Database.update_user(user_id, subscription=sub_type, expiry_date=expiry)
        await update.message.reply_text(f"✅ {sub_type.upper()} подписка активирована до {expiry}!")
    elif payment.invoice_payload.startswith('stars_'):
        amount = int(payment.invoice_payload.split('_')[1])
        Database.update_user(user_id, stars_balance=sqlite3.connect('bot.db').execute(
            'SELECT stars_balance + ? FROM users WHERE user_id = ?', 
            (amount, user_id)
        ).fetchone()[0])
        await update.message.reply_text(f"✅ Ваш баланс пополнен на {amount} Stars!")

# Админ-панель
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("⚙️ Настройки подписок", callback_data="admin_subscription_settings")]
    ]
    
    await update.message.reply_text(
        "🛠 Админ-панель",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    total_users = len(Database.get_all_users())
    payments_count, payments_sum = Database.get_payment_stats()
    
    await query.edit_message_text(
        f"📊 Статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💳 Платежи (30 дней): {payments_count} на сумму ${payments_sum or 0}"
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    users = Database.get_all_users()
    text = "👥 Последние пользователи:\n\n" + "\n".join(
        f"{user[0]}: @{user[1]} ({user[2]})" 
        for user in users[-10:]
    )
    await query.edit_message_text(text)

async def admin_subscription_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("🆓 Free", callback_data="set_free")],
        [InlineKeyboardButton("💎 PRO", callback_data="set_pro")],
        [InlineKeyboardButton("🚀 PREMIUM", callback_data="set_premium")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")]
    ]
    
    await query.edit_message_text(
        "Выберите тип подписки для настройки:",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def set_limits_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sub_type = query.data.split('_')[1]
    context.user_data['sub_type'] = sub_type
    
    await query.edit_message_text(
        f"Введите дневной и месячный лимиты для {sub_type.upper()} через пробел (например: 5 100):"
    )
    return SET_LIMITS

async def set_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        daily, monthly = map(int, update.message.text.split())
        sub_type = context.user_data['sub_type']
        SUBSCRIPTION_PLANS[sub_type]['daily_limit'] = daily
        SUBSCRIPTION_PLANS[sub_type]['monthly_limit'] = monthly
        
        await update.message.reply_text(
            f"✅ Лимиты для {sub_type.upper()} обновлены: {daily}/день, {monthly}/месяц"
        )
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Попробуйте снова.")
        return SET_LIMITS
    
    return ConversationHandler.END

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await admin_panel(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscription", show_subscription))
    app.add_handler(CommandHandler("generate", generate_video))
    app.add_handler(CommandHandler("search", search_videos))
    app.add_handler(CommandHandler("edit", edit_video))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    # Обработчики кнопок
    app.add_handler(CallbackQueryHandler(upgrade_subscription, pattern="^upgrade_"))
    app.add_handler(CallbackQueryHandler(buy_stars_menu, pattern="^buy_stars$"))
    app.add_handler(CallbackQueryHandler(process_stars_purchase, pattern="^stars_"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_subscription_settings, pattern="^admin_subscription_settings$"))
    app.add_handler(CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$"))
    
    # Платежи
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Настройка подписок
    sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_limits_start, pattern="^set_")],
        states={
            SET_LIMITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_limits)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(sub_conv)
    
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()