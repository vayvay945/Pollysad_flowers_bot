import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode, ChatType

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов (получить можно у @userinfobot)
ADMIN_IDS = [
    int(os.getenv("ADMIN_ID1", "0")), 
    int(os.getenv("ADMIN_ID2", "0"))
]

# ID канала (получить после добавления бота)
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # Добавим в переменные окружения

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
    """Приветствие и показ каталога"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    
    logger.info(f"Команда /start от пользователя {user_id} в чате {chat_id} (тип: {chat_type})")
    
    # Логируем ID канала для настройки
    if chat_type == ChatType.CHANNEL:
        logger.info(f"🔥 ID КАНАЛА: {chat_id} - добавьте это в переменную CHANNEL_ID")
    
    # В канале сразу показываем каталог
    if chat_type == ChatType.CHANNEL:
        await show_catalog_message(update, context)
    else:
        # В личке показываем меню
        await show_private_menu(update, context)

async def show_private_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню в личных сообщениях"""
    user = update.effective_user
    
    welcome_text = f"🌿 Добро пожаловать в наш цветочный магазин, {user.first_name}!"
    
    if is_admin(user.id):
        welcome_text += "\n\n🔧 Вы администратор. Доступны дополнительные функции."
    
    # Всегда показываем каталог как главную функцию
    await show_catalog_message(update, context, welcome_text)

async def show_catalog_message(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix_text=""):
    """Показывает каталог растений"""
    plants = load_plants()
    
    message_text = prefix_text + "\n\n🌱 **КАТАЛОГ РАСТЕНИЙ**\n\n" if prefix_text else "🌱 **КАТАЛОГ РАСТЕНИЙ**\n\n"
    
    if not plants:
        message_text += "😔 К сожалению, сейчас растений нет в наличии.\n\nСледите за обновлениями!"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
        return
    
    # Создаем кнопки для каждого растения
    keyboard = []
    available_count = 0
    
    for plant_id, plant_info in plants.items():
        if plant_info.get('available', True):
            # Проверяем, не забронировано ли
            bookings = load_bookings()
            is_booked = plant_id in bookings and bookings[plant_id]['status'] == 'active'
            
            if not is_booked:
                keyboard.append([InlineKeyboardButton(
                    f"🪴 {plant_info['name']} - {plant_info['price']}", 
                    callback_data=f"show_plant_{plant_id}"
                )])
                available_count += 1
    
    if available_count == 0:
        message_text += "🔒 Все растения сейчас забронированы.\n\nСледите за обновлениями!"
        keyboard = []
    else:
        message_text += f"Доступно растений: **{available_count}**\n\nВыберите растение для подробной информации:"
    
    # Добавляем админские кнопки если это админ
    if update.effective_user and is_admin(update.effective_user.id):
        if keyboard:
            keyboard.append([InlineKeyboardButton("➕ Добавить растение", callback_data="admin_add_plant")])
            keyboard.append([InlineKeyboardButton("📋 Активные брони", callback_data="admin_bookings")])
        else:
            keyboard = [
                [InlineKeyboardButton("➕ Добавить растение", callback_data="admin_add_plant")],
                [InlineKeyboardButton("📋 Активные брони", callback_data="admin_bookings")]
            ]
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
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
    message += f"💰 Цена: **{plant['price']}**\n\n"
    message += f"📝 **Описание:**\n{plant['description']}\n\n"
    
    keyboard = []
    
    if is_booked:
        message += "🔒 **ЗАБРОНИРОВАНО**"
    else:
        message += "✅ **ДОСТУПНО ДЛЯ БРОНИ**"
        keyboard.append([InlineKeyboardButton("📞 Забронировать", callback_data=f"book_plant_{plant_id}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog")])
    
    # Админские кнопки
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("🗑 Удалить растение", callback_data=f"admin_delete_{plant_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Если есть фото, отправляем с фото
    if plant.get('photo_file_id'):
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=plant['photo_file_id'],
                    caption=message,
                    parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=reply_markup
            )
        except:
            # Если не получается отредактировать медиа, отправляем текстом
            await query.edit_message_text(
                message,
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
    """Начинает процесс бронирования - переводит в личку"""
    query = update.callback_query
    await query.answer()
    
    plant_id = query.data.replace("book_plant_", "")
    plants = load_plants()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено")
        return
    
    plant_name = plants[plant_id]['name']
    bot_username = context.bot.username
    
    # Создаем ссылку на бота с параметром
    bot_link = f"https://t.me/{bot_username}?start=book_{plant_id}"
    
    keyboard = [
        [InlineKeyboardButton("📞 Перейти к бронированию", url=bot_link)],
        [InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📞 **Бронирование: {plant_name}**\n\n"
        f"Для бронирования нажмите кнопку ниже.\n"
        f"Вы перейдете в личную переписку с ботом для указания контактных данных.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_start_parameter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает параметры команды /start"""
    if not context.args:
        return await show_private_menu(update, context)
    
    param = context.args[0]
    
    if param.startswith("book_"):
        plant_id = param.replace("book_", "")
        plants = load_plants()
        
        if plant_id not in plants:
            await update.message.reply_text("❌ Растение не найдено")
            return
        
        # Проверяем, не забронировано ли уже
        bookings = load_bookings()
        if plant_id in bookings and bookings[plant_id]['status'] == 'active':
            await update.message.reply_text(
                "😔 Извините, это растение уже забронировано!\n\n"
                "Посмотрите другие доступные растения в каталоге."
            )
            return await show_catalog_message(update, context)
        
        context.user_data['booking_plant_id'] = plant_id
        plant_name = plants[plant_id]['name']
        
        await update.message.reply_text(
            f"📞 **Бронирование растения: {plant_name}**\n\n"
            f"Для бронирования нам нужны ваши контактные данные.\n\n"
            f"Введите ваше имя:",
            parse_mode=ParseMode.MARKDOWN
        )
        return BOOKING_NAME
    
    # Если параметр неизвестный, показываем обычное меню
    return await show_private_menu(update, context)

# ========== ПРОЦЕСС БРОНИРОВАНИЯ В ЛИЧКЕ ==========

async def booking_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает имя для бронирования"""
    context.user_data['booking_name'] = update.message.text.strip()
    
    await update.message.reply_text(
        "📱 Отлично! Теперь введите ваш номер телефона:"
    )
    return BOOKING_PHONE

async def booking_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает телефон для бронирования"""
    context.user_data['booking_phone'] = update.message.text.strip()
    
    await update.message.reply_text(
        "💬 Почти готово! Добавьте комментарий к заказу (или напишите 'нет', если комментария нет):"
    )
    return BOOKING_COMMENT

async def booking_get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает комментарий и завершает бронирование"""
    comment = update.message.text.strip() if update.message.text.strip().lower() != 'нет' else ""
    
    # Получаем данные бронирования
    plant_id = context.user_data.get('booking_plant_id')
    name = context.user_data.get('booking_name')
    phone = context.user_data.get('booking_phone')
    
    if not plant_id or not name or not phone:
        await update.message.reply_text("❌ Ошибка при бронировании. Попробуйте еще раз.")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Загружаем данные
    plants = load_plants()
    bookings = load_bookings()
    
    if plant_id not in plants:
        await update.message.reply_text("❌ Растение не найдено.")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Проверяем, не забронировано ли уже
    if plant_id in bookings and bookings[plant_id]['status'] == 'active':
        await update.message.reply_text(
            "😔 Извините, это растение уже забронировано!\n\n"
            "Посмотрите другие доступные растения."
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Создаем бронь
    booking_data = {
        'plant_id': plant_id,
        'plant_name': plants[plant_id]['name'],
        'plant_price': plants[plant_id]['price'],
        'user_id': update.effective_user.id,
        'user_name': name,
        'user_phone': phone,
        'comment': comment,
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
    }
    
    bookings[plant_id] = booking_data
    save_bookings(bookings)
    
    # Уведомляем пользователя
    await update.message.reply_text(
        f"✅ **Заявка на бронирование отправлена!**\n\n"
        f"🪴 Растение: **{plants[plant_id]['name']}**\n"
        f"💰 Цена: **{plants[plant_id]['price']}**\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"💬 Комментарий: {comment if comment else 'нет'}\n\n"
        f"⏰ Администратор свяжется с вами в течение 24 часов для подтверждения.",
        parse_mode=ParseMode.MARKDOWN
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
        if admin_id > 0:  # Проверяем что ID валидный
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

async def admin_add_plant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления растения через callback"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ У вас нет прав для этого действия")
        return
    
    await query.edit_message_text(
        "➕ **Добавление нового растения**\n\n"
        "Введите название растения:",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADDING_NAME

async def admin_show_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает активные брони"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ У вас нет прав для этого действия")
        return
    
    bookings = load_bookings()
    active_bookings = {k: v for k, v in bookings.items() 
                      if v['status'] in ['pending', 'active']}
    
    if not active_bookings:
        keyboard = [[InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 **Активных броней нет**",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = "📋 **АКТИВНЫЕ БРОНИ:**\n\n"
    keyboard = []
    
    for plant_id, booking in active_bookings.items():
        status_emoji = "⏳" if booking['status'] == 'pending' else "✅"
        status_text = "Ожидает" if booking['status'] == 'pending' else "Подтверждено"
        
        message += f"{status_emoji} **{booking['plant_name']}** - {booking['plant_price']}\n"
        message += f"👤 {booking['user_name']} | 📱 {booking['user_phone']}\n"
        message += f"📅 {datetime.fromisoformat(booking['created_at']).strftime('%d.%m %H:%M')}"
        message += f" | 📊 {status_text}\n\n"
        
        if booking['status'] == 'pending':
            keyboard.extend([
                [
                    InlineKeyboardButton(f"✅ Подтвердить {booking['plant_name'][:20]}...", 
                                       callback_data=f"confirm_booking_{plant_id}"),
                ],
                [
                    InlineKeyboardButton(f"❌ Отклонить {booking['plant_name'][:20]}...", 
                                       callback_data=f"reject_booking_{plant_id}")
                ]
            ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# ========== ДОБАВЛЕНИЕ РАСТЕНИЙ ==========

async def add_plant_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает название растения"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этого действия")
        return ConversationHandler.END
    
    context.user_data['plant_name'] = update.message.text.strip()
    await update.message.reply_text("💰 Введите цену растения (например: 1500₽):")
    return ADDING_PRICE

async def add_plant_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает цену растения"""
    context.user_data['plant_price'] = update.message.text.strip()
    await update.message.reply_text("📝 Введите описание растения (размер, уход, особенности):")
    return ADDING_DESCRIPTION

async def add_plant_get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает описание растения"""
    context.user_data['plant_description'] = update.message.text.strip()
    await update.message.reply_text("📸 Отправьте фото растения или напишите 'пропустить':")
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
    elif update.message.text and update.message.text.strip().lower() != 'пропустить':
        await update.message.reply_text("❌ Пожалуйста, отправьте фото или напишите 'пропустить'")
        return ADDING_PHOTO
    
    plants[plant_id] = plant_data
    save_plants(plants)
    
    await update.message.reply_text(
        f"✅ **Растение успешно добавлено!**\n\n"
        f"🪴 Название: **{plant_data['name']}**\n"
        f"💰 Цена: **{plant_data['price']}**\n"
        f"📝 Описание: {plant_data['description'][:100]}...\n\n"
        f"Растение появится в каталоге канала.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Уведомляем канал об обновлении каталога
    if CHANNEL_ID != 0:
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"🆕 **Новое растение в каталоге!**\n\n"
                     f"🪴 **{plant_data['name']}** - {plant_data['price']}\n\n"
                     f"Для просмотра всего каталога используйте /catalog",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление в канал: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END

# ========== ОБРАБОТЧИКИ ПОДТВЕРЖДЕНИЯ/ОТКЛОНЕНИЯ БРОНЕЙ ==========

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает бронирование"""
    if not is_admin(update.effective_user.id):
        await update.callback_query.answer("❌ У вас нет прав для этого действия")
        return
    
    query = update.callback_query
    await query.answer()
    plant_id = query.data.replace("confirm_booking_", "")
    
    bookings = load_bookings()
    if plant_id not in bookings:
        await query.edit_message_text("❌ Бронирование не найдено")
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
                 f"🪴 Растение: **{booking['plant_name']}**\n"
                 f"💰 Цена: **{booking['plant_price']}**\n\n"
                 f"Ожидаем вас в магазине!\n"
                 f"📞 При вопросах звоните: [УКАЖИТЕ ВАШ ТЕЛЕФОН]",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить клиента: {e}")
    
    await query.edit_message_text(
        f"✅ **Бронирование подтверждено!**\n\n"
        f"🪴 {booking['plant_name']}\n"
        f"👤 Клиент: {booking['user_name']}\n"
        f"📱 Телефон: {booking['user_phone']}\n\n"
        f"Клиент уведомлен о подтверждении.",
        parse_mode=ParseMode.MARKDOWN
    )

async def reject_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклоняет бронирование"""
    if not is_admin(update.effective_user.id):
        await update.callback_query.answer("❌ У вас нет прав для этого действия")
        return
    
    query = update.callback_query
    await query.answer()
    plant_id = query.data.replace("reject_booking_", "")
    
    bookings = load_bookings()
    if plant_id not in bookings:
        await query.edit_message_text("❌ Бронирование не найдено")
        return
    
    booking = bookings[plant_id]
    del bookings[plant_id]
    save_bookings(bookings)
    
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            chat_id=booking['user_id'],
            text=f"😔 **К сожалению, ваше бронирование отклонено**\n\n"
                 f"🪴 Растение: **{booking['plant_name']}**\n\n"
                 f"Возможно, растение уже продано или недоступно.\n"
                 f"Посмотрите другие растения в каталоге.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить клиента: {e}")
    
    await query.edit_message_text(
        f"❌ **Бронирование отклонено**\n\n"
        f"🪴 {booking['plant_name']}\n"
        f"👤 Клиент: {booking['user_name']}\n\n"
        f"Клиент уведомлен об отклонении.",
        parse_mode=ParseMode.MARKDOWN
    )

# ========== ОБРАБОТКА CALLBACK ЗАПРОСОВ ==========

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("show_plant_"):
        await show_plant_details(update, context)
    elif query.data.startswith("book_plant_"):
        await start_booking(update, context)
    elif query.data == "back_to_catalog":
        await show_catalog_message(update, context)
    elif query.data == "admin_add_plant":
        return await admin_add_plant_callback(update, context)
    elif query.data == "admin_bookings":
        await admin_show_bookings(update, context)
    elif query.data.startswith("confirm_booking_"):
        await confirm_booking(update, context)
    elif query.data.startswith("reject_booking_"):
        await reject_booking(update, context)
    elif query.data.startswith("admin_delete_"):
        await admin_delete_plant(update, context)

async def admin_delete_plant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет растение (только для админов)"""
    if not is_admin(update.effective_user.id):
        await update.callback_query.answer("❌ У вас нет прав для этого действия")
        return
    
    query = update.callback_query
    await query.answer()
    
    plant_id = query.data.replace("admin_delete_", "")
    plants = load_plants()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено")
        return
    
    plant_name = plants[plant_id]['name']
    
    # Проверяем, есть ли активные брони
    bookings = load_bookings()
    if plant_id in bookings and bookings[plant_id]['status'] == 'active':
        await query.edit_message_text(
            f"❌ **Нельзя удалить растение**\n\n"
            f"🪴 {plant_name}\n\n"
            f"На это растение есть активная бронь!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Удаляем растение и связанные брони
    del plants[plant_id]
    save_plants(plants)
    
    if plant_id in bookings:
        del bookings[plant_id]
        save_bookings(bookings)
    
    await query.edit_message_text(
        f"✅ **Растение удалено**\n\n"
        f"🪴 {plant_name}\n\n"
        f"Растение больше не отображается в каталоге.",
        parse_mode=ParseMode.MARKDOWN
    )

# ========== КОМАНДЫ ДЛЯ КАНАЛА ==========

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /catalog - показывает каталог"""
    await show_catalog_message(update, context)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /info - информация о магазине"""
    info_text = (
        "🌿 **Наш цветочный магазин**\n\n"
        "Мы специализируемся на комнатных растениях и всём необходимом для их ухода.\n\n"
        "🕐 **Режим работы:** ежедневно с 10:00 до 20:00\n"
        "📍 **Адрес:** [УКАЖИТЕ ВАШ АДРЕС]\n"
        "📞 **Телефон:** [УКАЖИТЕ ВАШ ТЕЛЕФОН]\n"
        "📧 **Email:** [УКАЖИТЕ ВАШ EMAIL]\n\n"
        f"🤖 Для заказов пишите боту: @{context.bot.username}"
    )
    
    await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщения в канале"""
    # Логируем для получения ID канала
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    logger.info(f"Сообщение в {chat_type} {chat_id}: {update.message.text}")
    
    # В каналах отвечаем только на команды
    if chat_type == ChatType.CHANNEL and update.message.text:
        if update.message.text.startswith('/'):
            # Команды уже обработаны соответствующими handlers
            return
    
    # В группах и личных сообщениях можем отвечать на всё
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.PRIVATE]:
        return

# ========== MAIN ФУНКЦИЯ ==========

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Добавьте переменную окружения.")
        return
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик для добавления растений (только в личке)
    add_plant_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_plant_callback, pattern="^admin_add_plant$")],
        states={
            ADDING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plant_get_name)],
            ADDING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plant_get_price)],
            ADDING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_plant_get_description)],
            ADDING_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, add_plant_get_photo)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    # Обработчик для бронирования (только в личке)
    booking_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", handle_start_parameter, filters.ChatType.PRIVATE)
        ],
        states={
            BOOKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_get_name)],
            BOOKING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_get_phone)],
            BOOKING_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_get_comment)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    # Основные команды
    application.add_handler(CommandHandler("start", start, filters.ChatType.CHANNEL))
    application.add_handler(CommandHandler("start", handle_start_parameter, filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("catalog", catalog_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # Обработчики диалогов
    application.add_handler(add_plant_handler)
    application.add_handler(booking_handler)
    
    # Callback обработчики
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Обработчик всех остальных сообщений
    application.add_handler(MessageHandler(filters.TEXT, handle_channel_message))
    
    # Запуск бота
    logger.info("🤖 Бот для канала запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
