import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ (ОБЯЗАТЕЛЬНО ЗАПОЛНИТЕ!) ==========
BOT_TOKEN = "ВСТАВЬТЕ_СЮДА_ТОКЕН_ОТ_BOTFATHER"

# ID администраторов (получить можно у @userinfobot)
ADMIN_IDS = [
    123456789,  # Замените на реальный ID первого админа
    987654321   # Замените на реальный ID второго админа
]

# ID канала/группы где работает бот (получить можно добавив бота в канал)
CHANNEL_ID = -1001234567890  # Замените на реальный ID канала

# ========== ФАЙЛЫ ДЛЯ ХРАНЕНИЯ ДАННЫХ ==========
PLANTS_FILE = "plants.json"
BOOKINGS_FILE = "bookings.json"

# ========== СОСТОЯНИЯ ДЛЯ ДИАЛОГОВ ==========
ADDING_NAME, ADDING_DESCRIPTION, ADDING_PRICE, ADDING_PHOTO = range(4)
BOOKING_NAME, BOOKING_PHONE, BOOKING_COMMENT = range(3)

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ==========

def load_plants():
    """Загружает список растений из файла"""
    if os.path.exists(PLANTS_FILE):
        with open(PLANTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_plants(plants):
    """Сохраняет список растений в файл"""
    with open(PLANTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(plants, f, ensure_ascii=False, indent=2)

def load_bookings():
    """Загружает список броней из файла"""
    if os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_bookings(bookings):
    """Сохраняет список броней в файл"""
    with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и главное меню"""
    user = update.effective_user
    
    if is_admin(user.id):
        keyboard = [
            [KeyboardButton("🌱 Каталог растений")],
            [KeyboardButton("➕ Добавить растение"), KeyboardButton("❌ Удалить растение")],
            [KeyboardButton("📋 Активные брони"), KeyboardButton("⚙️ Управление")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🌱 Каталог растений")],
            [KeyboardButton("ℹ️ О магазине"), KeyboardButton("📞 Контакты")]
        ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🌿 Добро пожаловать в наш цветочный магазин, {user.first_name}!\n\n"
        "Выберите действие из меню:",
        reply_markup=reply_markup
    )

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает каталог растений"""
    plants = load_plants()
    
    if not plants:
        await update.message.reply_text("🤷‍♀️ К сожалению, сейчас растений нет в наличии")
        return
    
    # Создаем кнопки для каждого растения
    keyboard = []
    for plant_id, plant_info in plants.items():
        if plant_info.get('available', True):  # Показываем только доступные
            keyboard.append([InlineKeyboardButton(
                f"🪴 {plant_info['name']} - {plant_info['price']}", 
                callback_data=f"show_plant_{plant_id}"
            )])
    
    if not keyboard:
        await update.message.reply_text("🤷‍♀️ К сожалению, все растения сейчас забронированы")
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌱 Наши растения в наличии:\n\nВыберите растение для подробной информации:",
        reply_markup=reply_markup
    )

async def show_plant_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали конкретного растения"""
    query = update.callback_query
    await query.answer()
    
    plant_id = query.data.replace("show_plant_", "")
    plants = load_plants()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено")
        return
    
    plant = plants[plant_id]
    
    # Проверяем, забронировано ли растение
    bookings = load_bookings()
    is_booked = plant_id in bookings and bookings[plant_id]['status'] == 'active'
    
    message = f"🪴 **{plant['name']}**\n\n"
    message += f"💰 Цена: {plant['price']}\n\n"
    message += f"📝 Описание:\n{plant['description']}\n\n"
    
    if is_booked:
        message += "🔒 **ЗАБРОНИРОВАНО**"
        keyboard = [[InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog")]]
    else:
        message += "✅ **В НАЛИЧИИ**"
        keyboard = [
            [InlineKeyboardButton("📞 Забронировать", callback_data=f"book_plant_{plant_id}")],
            [InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Если есть фото, отправляем с фото
    if plant.get('photo_file_id'):
        await query.edit_message_caption(
            caption=message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

# ========== БРОНИРОВАНИЕ ==========

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс бронирования"""
    query = update.callback_query
    await query.answer()
    
    plant_id = query.data.replace("book_plant_", "")
    context.user_data['booking_plant_id'] = plant_id
    
    plants = load_plants()
    plant_name = plants[plant_id]['name']
    
    await query.edit_message_text(
        f"📞 Бронирование растения: **{plant_name}**\n\n"
        "Для бронирования нам нужны ваши контактные данные.\n\n"
        "Введите ваше имя:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return BOOKING_NAME

async def booking_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает имя для бронирования"""
    context.user_data['booking_name'] = update.message.text
    
    await update.message.reply_text(
        "📱 Отлично! Теперь введите ваш номер телефона:"
    )
    
    return BOOKING_PHONE

async def booking_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает телефон для бронирования"""
    context.user_data['booking_phone'] = update.message.text
    
    await update.message.reply_text(
        "💬 Почти готово! Оставьте комментарий (или напишите 'нет', если комментария нет):"
    )
    
    return BOOKING_COMMENT

async def booking_get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает комментарий и завершает бронирование"""
    comment = update.message.text if update.message.text.lower() != 'нет' else ""
    
    # Получаем данные бронирования
    plant_id = context.user_data['booking_plant_id']
    name = context.user_data['booking_name']
    phone = context.user_data['booking_phone']
    
    # Загружаем данные
    plants = load_plants()
    bookings = load_bookings()
    
    # Проверяем, не забронировано ли уже
    if plant_id in bookings and bookings[plant_id]['status'] == 'active':
        await update.message.reply_text("😔 Извините, это растение уже забронировано!")
        return ConversationHandler.END
    
    # Создаем бронь
    booking_id = f"{plant_id}_{update.effective_user.id}_{int(datetime.now().timestamp())}"
    
    booking_data = {
        'plant_id': plant_id,
        'plant_name': plants[plant_id]['name'],
        'user_id': update.effective_user.id,
        'user_name': name,
        'user_phone': phone,
        'comment': comment,
        'status': 'pending',  # pending -> active/rejected
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
    }
    
    bookings[plant_id] = booking_data
    save_bookings(bookings)
    
    # Уведомляем пользователя
    await update.message.reply_text(
        f"✅ Заявка на бронирование отправлена!\n\n"
        f"🪴 Растение: {plants[plant_id]['name']}\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"💬 Комментарий: {comment if comment else 'нет'}\n\n"
        f"⏰ Администратор свяжется с вами в течение 24 часов для подтверждения."
    )
    
    # Уведомляем админов
    admin_message = (
        f"🔔 **НОВАЯ ЗАЯВКА НА БРОНИРОВАНИЕ**\n\n"
        f"🪴 Растение: **{plants[plant_id]['name']}**\n"
        f"💰 Цена: {plants[plant_id]['price']}\n\n"
        f"👤 Клиент: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"💬 Комментарий: {comment if comment else 'нет'}\n"
        f"🆔 ID пользователя: {update.effective_user.id}\n\n"
        f"⏰ Заявка действительна до: {(datetime.now() + timedelta(hours=24)).strftime('%d.%m.%Y %H:%M')}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{plant_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_booking_{plant_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    return ConversationHandler.END

# ========== АДМИНСКИЕ ФУНКЦИИ ==========

async def add_plant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает добавление нового растения"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этого действия")
        return
    
    await update.message.reply_text(
        "➕ Добавление нового растения\n\n"
        "Введите название растения:"
    )
    
    return ADDING_NAME

async def add_plant_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает название растения"""
    context.user_data['plant_name'] = update.message.text
    
    await update.message.reply_text(
        "💰 Введите цену растения (например: 1500₽ или 1500 руб):"
    )
    
    return ADDING_PRICE

async def add_plant_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает цену растения"""
    context.user_data['plant_price'] = update.message.text
    
    await update.message.reply_text(
        "📝 Введите описание растения (размер, уход, особенности):"
    )
    
    return ADDING_DESCRIPTION

async def add_plant_get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает описание растения"""
    context.user_data['plant_description'] = update.message.text
    
    await update.message.reply_text(
        "📸 Отправьте фото растения или напишите 'пропустить' если фото нет:"
    )
    
    return ADDING_PHOTO

async def add_plant_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает фото и сохраняет растение"""
    plants = load_plants()
    
    # Генерируем уникальный ID для растения
    plant_id = f"plant_{len(plants) + 1}_{int(datetime.now().timestamp())}"
    
    plant_data = {
        'name': context.user_data['plant_name'],
        'price': context.user_data['plant_price'],
        'description': context.user_data['plant_description'],
        'available': True,
        'created_at': datetime.now().isoformat()
    }
    
    # Если отправлено фото, сохраняем file_id
    if update.message.photo:
        plant_data['photo_file_id'] = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.lower() != 'пропустить':
        await update.message.reply_text("❌ Пожалуйста, отправьте фото или напишите 'пропустить'")
        return ADDING_PHOTO
    
    plants[plant_id] = plant_data
    save_plants(plants)
    
    await update.message.reply_text(
        f"✅ Растение успешно добавлено!\n\n"
        f"🪴 Название: {plant_data['name']}\n"
        f"💰 Цена: {plant_data['price']}\n"
        f"📝 Описание: {plant_data['description'][:100]}..."
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ========== ОБРАБОТКА КНОПОК ==========

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на inline кнопки"""
    query = update.callback_query
    
    if query.data.startswith("show_plant_"):
        await show_plant_details(update, context)
    elif query.data.startswith("book_plant_"):
        return await start_booking(update, context)
    elif query.data == "back_to_catalog":
        await query.answer()
        await show_catalog_inline(query)
    elif query.data.startswith("confirm_booking_"):
        await confirm_booking(update, context)
    elif query.data.startswith("reject_booking_"):
        await reject_booking(update, context)

async def show_catalog_inline(query):
    """Показывает каталог в inline режиме"""
    plants = load_plants()
    
    if not plants:
        await query.edit_message_text("🤷‍♀️ К сожалению, сейчас растений нет в наличии")
        return
    
    keyboard = []
    for plant_id, plant_info in plants.items():
        if plant_info.get('available', True):
            keyboard.append([InlineKeyboardButton(
                f"🪴 {plant_info['name']} - {plant_info['price']}", 
                callback_data=f"show_plant_{plant_id}"
            )])
    
    if not keyboard:
        await query.edit_message_text("🤷‍♀️ К сожалению, все растения сейчас забронированы")
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🌱 Наши растения в наличии:\n\nВыберите растение для подробной информации:",
        reply_markup=reply_markup
    )

# ========== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ==========

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения из меню"""
    text = update.message.text
    
    if text == "🌱 Каталог растений":
        await show_catalog(update, context)
    elif text == "ℹ️ О магазине":
        await update.message.reply_text(
            "🌿 Наш цветочный магазин\n\n"
            "Мы специализируемся на комнатных растениях и всем необходимом для их ухода.\n\n"
            "🕐 Режим работы: ежедневно с 10:00 до 20:00\n"
            "📍 Адрес: [УКАЖИТЕ ВАШ АДРЕС]\n"
            "📞 Телефон: [УКАЖИТЕ ВАШ ТЕЛЕФОН]"
        )
    elif text == "📞 Контакты":
        await update.message.reply_text(
            "📞 Наши контакты:\n\n"
            "☎️ Телефон: [УКАЖИТЕ ВАШ ТЕЛЕФОН]\n"
            "📧 Email: [УКАЖИТЕ ВАШ EMAIL]\n"
            "📍 Адрес: [УКАЖИТЕ ВАШ АДРЕС]\n\n"
            "🕐 Режим работы:\n"
            "Пн-Вс: 10:00 - 20:00"
        )
    
    # Админские команды
    elif text == "➕ Добавить растение" and is_admin(update.effective_user.id):
        return await add_plant_start(update, context)
    elif text == "📋 Активные брони" and is_admin(update.effective_user.id):
        await show_active_bookings(update, context)

async def show_active_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает активные брони (только для админов)"""
    bookings = load_bookings()
    
    active_bookings = {k: v for k, v in bookings.items() 
                      if v['status'] in ['pending', 'active']}
    
    if not active_bookings:
        await update.message.reply_text("📋 Активных броней нет")
        return
    
    message = "📋 **АКТИВНЫЕ БРОНИ:**\n\n"
    
    for plant_id, booking in active_bookings.items():
        status_emoji = "⏳" if booking['status'] == 'pending' else "✅"
        status_text = "Ожидает подтверждения" if booking['status'] == 'pending' else "Подтверждено"
        
        message += f"{status_emoji} **{booking['plant_name']}**\n"
        message += f"👤 {booking['user_name']}\n"
        message += f"📱 {booking['user_phone']}\n"
        message += f"📅 {datetime.fromisoformat(booking['created_at']).strftime('%d.%m.%Y %H:%M')}\n"
        message += f"📊 Статус: {status_text}\n\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает бронирование"""
    if not is_admin(update.effective_user.id):
        await update.callback_query.answer("❌ У вас нет прав для этого действия")
        return
    
    query = update.callback_query
    plant_id = query.data.replace("confirm_booking_", "")
    
    bookings = load_bookings()
    
    if plant_id not in bookings:
        await query.answer("❌ Бронирование не найдено")
        return
    
    booking = bookings[plant_id]
    booking['status'] = 'active'
    booking['confirmed_by'] = update.effective_user.id
    booking['confirmed_at'] = datetime.now().isoformat()
    
    save_bookings(bookings)
    
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            chat_id=booking['user_id'],
            text=f"✅ **БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО!**\n\n"
                 f"🪴 Растение: {booking['plant_name']}\n\n"
                 f"Ожидаем вас в магазине!\n"
                 f"📞 При возникновении вопросов звоните: [УКАЖИТЕ ТЕЛЕФОН]",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить клиента: {e}")
    
    await query.edit_message_text(
        f"✅ Бронирование подтверждено!\n\n"
        f"Клиент {booking['user_name']} уведомлен."
    )

async def reject_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклоняет бронирование"""
    if not is_admin(update.effective_user.id):
        await update.callback_query.answer("❌ У вас нет прав для этого действия")
        return
    
    query = update.callback_query
    plant_id = query.data.replace("reject_booking_", "")
    
    bookings = load_bookings()
    
    if plant_id not in bookings:
        await query.answer("❌ Бронирование не найдено")
        return
    
    booking = bookings[plant_id]
    
    # Удаляем бронирование
    del bookings[plant_id]
    save_bookings(bookings)
    
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            chat_id=booking['user_id'],
            text=f"😔 К сожалению, ваше бронирование отклонено\n\n"
                 f"🪴 Растение: {booking['plant_name']}\n\n"
                 f"Возможно, растение уже продано или недоступно.\n"
                 f"Посмотрите другие растения в каталоге или свяжитесь с нами."
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить клиента: {e}")
    
    await query.edit_message_text(
        f"❌ Бронирование отклонено.\n\n"
        f"Клиент {booking['user_name']} уведомлен."
    )

# ========== ЗАПУСК БОТА ==========

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик для добавления растений
    add_plant_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Добавить растение"), add_plant_start)],
        states={
            ADDING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plant_get_name)],
            ADDING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plant_get_price)],
            ADDING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plant_get_description)],
            ADDING_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, add_plant_get_photo)],
        },
        fallbacks=[]
    )
    
    # Обработчик для бронирования
    booking_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_booking, pattern="^book_plant_")],
        states={
            BOOKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_get_name)],
            BOOKING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_get_phone)],
            BOOKING_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_get_comment)],
        },
        fallbacks=[]
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_plant_handler)
    application.add_handler(booking_handler)
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Запуск бота
    print("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
