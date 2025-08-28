import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')

# ИСПРАВЛЕНО: Получение админов из ADMIN_ID1, ADMIN_ID2, etc.
ADMIN_IDS = []

# Собираем всех админов из переменных ADMIN_ID1, ADMIN_ID2, ADMIN_ID3, etc.
for i in range(1, 10):  # Проверяем до ADMIN_ID9
    admin_id = os.getenv(f'ADMIN_ID{i}')
    if admin_id and admin_id.isdigit():
        ADMIN_IDS.append(int(admin_id))

# Также проверим стандартные варианты
admin_ids_str = os.getenv('ADMIN_IDS') or os.getenv('ADMIN_ID') or os.getenv('ADMINS') or ''
if admin_ids_str:
    try:
        if ',' in admin_ids_str:
            additional_admins = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]
            ADMIN_IDS.extend(additional_admins)
        elif admin_ids_str.isdigit():
            ADMIN_IDS.append(int(admin_ids_str))
    except Exception as e:
        logger.error(f"Ошибка парсинга дополнительных админов: {e}")

# Удаляем дубликаты
ADMIN_IDS = list(set(ADMIN_IDS))

# Получение ID канала (если нужно)
CHANNEL_ID = os.getenv('CHANNEL_ID')

# ОТЛАДОЧНАЯ ИНФОРМАЦИЯ
logger.info(f"BOT_TOKEN найден: {'Да' if BOT_TOKEN else 'Нет'}")
logger.info(f"ADMIN_IDS загружены: {ADMIN_IDS}")
logger.info(f"CHANNEL_ID: {CHANNEL_ID}")
logger.info(f"Количество админов: {len(ADMIN_IDS)}")

# Показываем все найденные переменные с админами
for i in range(1, 10):
    admin_var = os.getenv(f'ADMIN_ID{i}')
    if admin_var:
        logger.info(f"ADMIN_ID{i}: {admin_var}")

# Состояния для машины состояний
WAITING_PLANT_NAME = 'waiting_plant_name'
WAITING_PLANT_DESCRIPTION = 'waiting_plant_description'
WAITING_PLANT_PRICE = 'waiting_plant_price'
WAITING_PLANT_QUANTITY = 'waiting_plant_quantity'
WAITING_PLANT_PHOTO = 'waiting_plant_photo'
WAITING_BOOKING_NAME = 'waiting_booking_name'
WAITING_BOOKING_PHONE = 'waiting_booking_phone'

# Глобальное хранилище состояний пользователей
user_states = {}
temp_plant_data = {}
temp_booking_data = {}

def load_json_file(filename):
    """Загрузка данных из JSON файла с обработкой ошибок"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                return json.load(file)
        return {}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Ошибка загрузки файла {filename}: {e}")
        return {}

def save_json_file(filename, data):
    """Сохранение данных в JSON файл с обработкой ошибок"""
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения файла {filename}: {e}")
        return False

def load_plants():
    """Загрузка списка растений"""
    return load_json_file('plants.json')

def save_plants(plants):
    """Сохранение списка растений"""
    return save_json_file('plants.json', plants)

def load_bookings():
    """Загрузка списка бронирований"""
    return load_json_file('bookings.json')

def save_bookings(bookings):
    """Сохранение списка бронирований"""
    return save_json_file('bookings.json', bookings)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "без_username"
    
    # ОТЛАДОЧНАЯ ИНФОРМАЦИЯ
    logger.info(f"Пользователь {user_id} (@{username}) запустил бота")
    logger.info(f"Проверяем права админа: {user_id} в {ADMIN_IDS} = {user_id in ADMIN_IDS}")
    
    # Очистка состояния пользователя
    user_states.pop(user_id, None)
    temp_plant_data.pop(user_id, None)
    temp_booking_data.pop(user_id, None)
    
    # Создание клавиатуры
    is_admin = user_id in ADMIN_IDS
    
    if is_admin:
        keyboard = [
            [KeyboardButton("📱 Каталог растений")],
            [KeyboardButton("➕ Добавить растение"), KeyboardButton("❌ Удалить растение")],
            [KeyboardButton("📋 Управление заказами")],
            [KeyboardButton("🔧 Debug Info")]
        ]
        logger.info(f"✅ Показываем АДМИНСКУЮ клавиатуру для пользователя {user_id}")
    else:
        keyboard = [
            [KeyboardButton("📱 Каталог растений")],
            [KeyboardButton("ℹ️ Проверить права")]
        ]
        logger.info(f"👤 Показываем обычную клавиатуру для пользователя {user_id}")
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_msg = "🌸 Добро пожаловать в магазин цветов Polly's Garden!\n\n"
    if is_admin:
        welcome_msg += f"🔑 ВЫ АДМИНИСТРАТОР (ID: {user_id})\n"
        welcome_msg += f"👥 Всего админов в системе: {len(ADMIN_IDS)}\n"
        welcome_msg += f"📋 Список админов: {ADMIN_IDS}"
    else:
        welcome_msg += f"👤 Ваш ID: {user_id}\n"
        welcome_msg += f"📋 Админы системы: {ADMIN_IDS}\n"
        welcome_msg += "Выберите действие из меню ниже."
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ каталога растений"""
    plants = load_plants()
    
    if not plants:
        await update.message.reply_text("🌱 Каталог пуст. Растения пока не добавлены.")
        return
    
    keyboard = []
    for plant_id, plant_data in plants.items():
        availability = "✅" if plant_data.get('quantity', 0) > 0 else "❌"
        button_text = f"{availability} {plant_data['name']} - {plant_data['price']}₽"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plant_{plant_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌸 Каталог наших растений:\n\n"
        "✅ - В наличии\n"
        "❌ - Нет в наличии\n\n"
        "Выберите растение для просмотра:",
        reply_markup=reply_markup
    )

async def handle_plant_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора растения из каталога"""
    query = update.callback_query
    await query.answer()
    
    plant_id = query.data.split('_')[1]
    plants = load_plants()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено!")
        return
    
    plant = plants[plant_id]
    
    message_text = f"🌸 **{plant['name']}**\n\n"
    message_text += f"📝 Описание: {plant['description']}\n"
    message_text += f"💰 Цена: {plant['price']}₽\n"
    message_text += f"📦 В наличии: {plant['quantity']} шт.\n"
    
    keyboard = []
    if plant['quantity'] > 0:
        keyboard.append([InlineKeyboardButton("🛒 Забронировать", callback_data=f"book_{plant_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к каталогу", callback_data="back_to_catalog")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if 'photo_file_id' in plant:
        try:
            await query.message.reply_photo(
                photo=plant['photo_file_id'],
                caption=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            await query.delete_message()
        except:
            await query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    else:
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса бронирования"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    plant_id = query.data.split('_')[1]
    plants = load_plants()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено!")
        return
    
    plant = plants[plant_id]
    
    if plant['quantity'] <= 0:
        await query.edit_message_text("❌ К сожалению, это растение закончилось!")
        return
    
    temp_booking_data[user_id] = {
        'plant_id': plant_id,
        'plant_name': plant['name'],
        'price': plant['price']
    }
    
    user_states[user_id] = WAITING_BOOKING_NAME
    
    await query.edit_message_text(
        f"🛒 Бронирование: {plant['name']}\n\n"
        f"💰 Цена: {plant['price']}₽\n\n"
        "👤 Пожалуйста, введите ваше имя:"
    )

async def back_to_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к каталогу"""
    query = update.callback_query
    await query.answer()
    
    plants = load_plants()
    
    if not plants:
        await query.edit_message_text("🌱 Каталог пуст. Растения пока не добавлены.")
        return
    
    keyboard = []
    for plant_id, plant_data in plants.items():
        availability = "✅" if plant_data.get('quantity', 0) > 0 else "❌"
        button_text = f"{availability} {plant_data['name']} - {plant_data['price']}₽"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plant_{plant_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🌸 Каталог наших растений:\n\n"
        "✅ - В наличии\n"
        "❌ - Нет в наличии\n\n"
        "Выберите растение для просмотра:",
        reply_markup=reply_markup
    )

async def add_plant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления нового растения"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(f"❌ У вас нет прав для выполнения этой операции.\nВаш ID: {user_id}\nАдмины: {ADMIN_IDS}")
        return
    
    user_states[user_id] = WAITING_PLANT_NAME
    temp_plant_data[user_id] = {}
    
    await update.message.reply_text("🌱 Добавление нового растения\n\n📝 Введите название растения:")

async def handle_plant_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия растения"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_PLANT_NAME:
        return
    
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Название должно содержать минимум 2 символа. Попробуйте снова:")
        return
    
    temp_plant_data[user_id]['name'] = name
    user_states[user_id] = WAITING_PLANT_DESCRIPTION
    
    await update.message.reply_text("📋 Введите описание растения:")

async def handle_plant_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода описания растения"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_PLANT_DESCRIPTION:
        return
    
    description = update.message.text.strip()
    if len(description) < 5:
        await update.message.reply_text("❌ Описание должно содержать минимум 5 символов. Попробуйте снова:")
        return
    
    temp_plant_data[user_id]['description'] = description
    user_states[user_id] = WAITING_PLANT_PRICE
    
    await update.message.reply_text("💰 Введите цену растения (только число, например: 1500):")

async def handle_plant_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода цены растения"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_PLANT_PRICE:
        return
    
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            raise ValueError("Цена должна быть положительной")
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректную цену (например: 1500 или 1500.50):")
        return
    
    temp_plant_data[user_id]['price'] = price
    user_states[user_id] = WAITING_PLANT_QUANTITY
    
    await update.message.reply_text("📦 Введите количество растений в наличии:")

async def handle_plant_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода количества растений"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_PLANT_QUANTITY:
        return
    
    try:
        quantity = int(update.message.text.strip())
        if quantity < 0:
            raise ValueError("Количество не может быть отрицательным")
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректное количество (целое число):")
        return
    
    temp_plant_data[user_id]['quantity'] = quantity
    user_states[user_id] = WAITING_PLANT_PHOTO
    
    await update.message.reply_text("📷 Отправьте фото растения или введите 'пропустить', чтобы добавить без фото:")

async def handle_plant_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото растения и завершение добавления"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_PLANT_PHOTO:
        return
    
    plant_data = temp_plant_data[user_id]
    
    if update.message.photo:
        plant_data['photo_file_id'] = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.lower() in ['пропустить', 'skip']:
        pass
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте фото или введите 'пропустить':")
        return
    
    plants = load_plants()
    plant_id = str(len(plants) + 1)
    plants[plant_id] = plant_data
    
    if save_plants(plants):
        user_states.pop(user_id, None)
        temp_plant_data.pop(user_id, None)
        
        await update.message.reply_text(
            f"✅ Растение успешно добавлено!\n\n"
            f"🌸 Название: {plant_data['name']}\n"
            f"📋 Описание: {plant_data['description']}\n"
            f"💰 Цена: {plant_data['price']}₽\n"
            f"📦 Количество: {plant_data['quantity']} шт."
        )
    else:
        await update.message.reply_text("❌ Ошибка при сохранении растения. Попробуйте позже.")

async def handle_booking_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени при бронировании"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_BOOKING_NAME:
        return
    
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Пожалуйста, введите корректное имя (минимум 2 символа):")
        return
    
    temp_booking_data[user_id]['customer_name'] = name
    user_states[user_id] = WAITING_BOOKING_PHONE
    
    await update.message.reply_text("📞 Теперь введите ваш номер телефона для связи:")

async def handle_booking_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода телефона и завершение бронирования"""
    user_id = update.effective_user.id
    
    if user_states.get(user_id) != WAITING_BOOKING_PHONE:
        return
    
    phone = update.message.text.strip()
    if len(phone) < 10:
        await update.message.reply_text("❌ Пожалуйста, введите корректный номер телефона:")
        return
    
    booking_data = temp_booking_data[user_id]
    booking_data.update({
        'customer_phone': phone,
        'user_id': user_id,
        'username': update.effective_user.username or "Не указан",
        'booking_time': datetime.now().isoformat(),
        'status': 'pending'
    })
    
    bookings = load_bookings()
    booking_id = str(len(bookings) + 1)
    bookings[booking_id] = booking_data
    
    if save_bookings(bookings):
        plants = load_plants()
        plant_id = booking_data['plant_id']
        if plant_id in plants:
            plants[plant_id]['quantity'] -= 1
            save_plants(plants)
        
        user_states.pop(user_id, None)
        temp_booking_data.pop(user_id, None)
        
        await update.message.reply_text(
            f"✅ Бронирование успешно создано!\n\n"
            f"🆔 Номер заказа: {booking_id}\n"
            f"🌸 Растение: {booking_data['plant_name']}\n"
            f"💰 Цена: {booking_data['price']}₽\n\n"
            f"📞 С вами свяжутся по номеру: {phone}\n\n"
            f"Администратор обработает ваш заказ в ближайшее время."
        )
        
        # Уведомление админов
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 Новое бронирование!\n\n"
                         f"🆔 Заказ #{booking_id}\n"
                         f"👤 Клиент: {booking_data['customer_name']}\n"
                         f"📞 Телефон: {booking_data['customer_phone']}\n"
                         f"🌸 Растение: {booking_data['plant_name']}\n"
                         f"💰 Цена: {booking_data['price']}₽"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении бронирования. Попробуйте позже.")

async def check_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка прав пользователя"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Не указан"
    
    # Показываем все переменные окружения для отладки
    admin_vars = {}
    for i in range(1, 10):
        admin_var = os.getenv(f'ADMIN_ID{i}')
        if admin_var:
            admin_vars[f'ADMIN_ID{i}'] = admin_var
    
    message = f"""
🔍 **ПОЛНАЯ ОТЛАДОЧНАЯ ИНФОРМАЦИЯ**

👤 **Ваши данные:**
• ID: `{user_id}`
• Username: @{username}
• Статус: {'🔑 АДМИНИСТРАТОР' if user_id in ADMIN_IDS else '👤 Обычный пользователь'}

📊 **Система админов:**
• Загружено админов: {len(ADMIN_IDS)}
• Список: {ADMIN_IDS}

🔧 **Переменные Railway:**
• BOT_TOKEN: {'✅ Найден' if BOT_TOKEN else '❌ Отсутствует'}
• CHANNEL_ID: {CHANNEL_ID or '❌ Не установлен'}

**Найденные ADMIN_ID переменные:**
{chr(10).join([f'• {k}: {v}' for k, v in admin_vars.items()]) if admin_vars else '❌ Не найдено переменных ADMIN_ID*'}

💡 **Для админских прав добавьте в Railway:**
`ADMIN_ID1 = {user_id}`
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная отладочная информация для админов"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await check_rights(update, context)
        return
    
    plants = load_plants()
    bookings = load_bookings()
    
    debug_text = f"""
🔧 **АДМИНСКАЯ ПАНЕЛЬ ОТЛАДКИ**

**🌸 База данных:**
• Растений: {len(plants)}
• Заказов: {len(bookings)}
• Активных состояний: {len(user_states)}

**👥 Пользователи:**
• Добавляют растения: {len(temp_plant_data)}
• Бронируют: {len(temp_booking_data)}

**📁 Файлы:**
• plants.json: {'✅ Есть' if os.path.exists('plants.json') else '❌ Нет'}
• bookings.json: {'✅ Есть' if os.path.exists('bookings.json') else '❌ Нет'}

**🔧 Environment:**
• Админов: {len(ADMIN_IDS)} - {ADMIN_IDS}
• Channel: {CHANNEL_ID or 'Не установлен'}
"""
    
    await update.message.reply_text(debug_text, parse_mode='Markdown')

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Проверяем состояния пользователя
    state = user_states.get(user_id)
    if state == WAITING_PLANT_NAME:
        await handle_plant_name(update, context)
        return
    elif state == WAITING_PLANT_DESCRIPTION:
        await handle_plant_description(update, context)
        return
    elif state == WAITING_PLANT_PRICE:
        await handle_plant_price(update, context)
        return
    elif state == WAITING_PLANT_QUANTITY:
        await handle_plant_quantity(update, context)
        return
    elif state == WAITING_PLANT_PHOTO:
        await handle_plant_photo(update, context)
        return
    elif state == WAITING_BOOKING_NAME:
        await handle_booking_name(update, context)
        return
    elif state == WAITING_BOOKING_PHONE:
        await handle_booking_phone(update, context)
        return
    
    # Обработка команд через кнопки
    if text == "📱 Каталог растений":
        await show_catalog(update, context)
    elif text == "➕ Добавить растение":
        await add_plant_start(update, context)
    elif text == "📋 Управление заказами":
        if user_id in ADMIN_IDS:
            bookings = load_bookings()
            if bookings:
                msg = "📋 **Заказы:**\n\n"
                for booking_id, booking in bookings.items():
                    status_emoji = "⏳" if booking.get('status') == 'pending' else "✅"
                    msg += f"{status_emoji} #{booking_id}: {booking['plant_name']} - {booking['customer_name']}\n"
                await update.message.reply_text(msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("📋 Заказов пока нет.")
        else:
            await update.message.reply_text("❌ У вас нет прав для выполнения этой операции.")
    elif text == "❌ Удалить растение":
        if user_id in ADMIN_IDS:
            await update.message.reply_text("🔧 Функция удаления в разработке.")
        else:
            await update.message.reply_text("❌ У вас нет прав для выполнения этой операции.")
    elif text == "🔧 Debug Info":
        await debug_info(update, context)
    elif text == "ℹ️ Проверить права":
        await check_rights(update, context)
    else:
        await update.message.reply_text("❓ Используйте кнопки меню или команду /start")

async def handle_photo_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото"""
    user_id = update.effective_user.id
    if user_states.get(user_id) == WAITING_PLANT_PHOTO:
        await handle_plant_photo(update, context)

async def handle_callback_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    query = update.callback_query
    data = query.data
    
    if data.startswith("plant_"):
        await handle_plant_selection(update, context)
    elif data.startswith("book_"):
        await start_booking(update, context)
    elif data == "back_to_catalog":
        await back_to_catalog(update, context)
    else:
        await query.answer("❌ Неизвестная команда")

def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден! Проверьте переменные окружения Railway.")
        return
    
    logger.info(f"🚀 Запуск бота с {len(ADMIN_IDS)} администраторами: {ADMIN_IDS}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("debug", check_rights))
    application.add_handler(CallbackQueryHandler(handle_callback_queries))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_messages))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    logger.info("✅ Бот готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
