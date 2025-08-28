import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatType

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# КОНФИГУРАЦИЯ
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID1", "0")), int(os.getenv("ADMIN_ID2", "0"))]
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# ФАЙЛЫ
PLANTS_FILE = "plants.json"
BOOKINGS_FILE = "bookings.json"

# СОСТОЯНИЯ (простые, без ConversationHandler)
user_states = {}

def load_plants():
    if os.path.exists(PLANTS_FILE):
        with open(PLANTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_plants(plants):
    with open(PLANTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(plants, f, ensure_ascii=False, indent=2)

def load_bookings():
    if os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_bookings(bookings):
    with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    chat_type = update.effective_chat.type
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None
    
    logger.info(f"/start от {user_id} в {chat_type} {chat_id}")
    
    if chat_type == ChatType.CHANNEL:
        logger.info(f"🔥 ID КАНАЛА: {chat_id}")
    
    # Проверяем deep link для бронирования
    if chat_type == ChatType.PRIVATE and context.args:
        param = context.args[0]
        if param.startswith("book_"):
            plant_id = param.replace("book_", "")
            await start_booking(update, context, plant_id)
            return
    
    # Показываем каталог
    await show_catalog(update, context)

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает каталог растений"""
    plants = load_plants()
    bookings = load_bookings()
    
    text = "🌱 **КАТАЛОГ РАСТЕНИЙ**\n\n"
    keyboard = []
    
    if not plants:
        text += "😔 Растений пока нет в наличии."
    else:
        available = 0
        for plant_id, plant in plants.items():
            if plant_id not in bookings:  # Не забронировано
                keyboard.append([InlineKeyboardButton(
                    f"🪴 {plant['name']} - {plant['price']}", 
                    callback_data=f"plant_{plant_id}"
                )])
                available += 1
        
        if available == 0:
            text += "🔒 Все растения сейчас забронированы."
        else:
            text += f"Доступно: **{available}** растений\n\nВыберите для подробностей:"
    
    # Админские кнопки
    if update.effective_user and is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("➕ Добавить растение", callback_data="admin_add")])
        keyboard.append([InlineKeyboardButton("📋 Брони", callback_data="admin_bookings")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    # Отправляем сообщение
    if update.callback_query:
        # Безопасное редактирование
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except:
            # Если не получается редактировать - удаляем и отправляем новое
            try:
                await update.callback_query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def show_plant(update: Update, context: ContextTypes.DEFAULT_TYPE, plant_id: str):
    """Показывает детали растения"""
    query = update.callback_query
    plants = load_plants()
    bookings = load_bookings()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено")
        return
    
    plant = plants[plant_id]
    is_booked = plant_id in bookings
    
    text = f"🪴 **{plant['name']}**\n\n"
    text += f"💰 Цена: **{plant['price']}**\n\n"
    text += f"📝 {plant['description']}\n\n"
    
    keyboard = []
    
    if is_booked:
        text += "🔒 **ЗАБРОНИРОВАНО**"
    else:
        text += "✅ **ДОСТУПНО**"
        keyboard.append([InlineKeyboardButton("📞 Забронировать", callback_data=f"book_{plant_id}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_catalog")])
    
    # Админские кнопки
    if update.effective_user and is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{plant_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Безопасное редактирование
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_booking_button(update: Update, context: ContextTypes.DEFAULT_TYPE, plant_id: str):
    """Обрабатывает кнопку бронирования"""
    query = update.callback_query
    plants = load_plants()
    
    if plant_id not in plants:
        await query.edit_message_text("❌ Растение не найдено")
        return
    
    plant_name = plants[plant_id]['name']
    bot_username = context.bot.username
    
    # Ссылка для перехода в личку
    bot_link = f"https://t.me/{bot_username}?start=book_{plant_id}"
    
    keyboard = [
        [InlineKeyboardButton("📞 Перейти к бронированию", url=bot_link)],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"plant_{plant_id}")]
    ]
    
    text = f"📞 **Бронирование: {plant_name}**\n\nНажмите кнопку для перехода в личку с ботом:"
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, plant_id: str):
    """Начинает процесс бронирования в личке"""
    plants = load_plants()
    bookings = load_bookings()
    
    if plant_id not in plants:
        await update.message.reply_text("❌ Растение не найдено")
        return
    
    if plant_id in bookings:
        await update.message.reply_text("😔 Это растение уже забронировано!")
        return
    
    plant_name = plants[plant_id]['name']
    user_id = update.effective_user.id
    
    # Сохраняем состояние пользователя
    user_states[user_id] = {"action": "booking", "plant_id": plant_id, "step": "name"}
    
    await update.message.reply_text(
        f"📞 **Бронирование: {plant_name}**\n\nВведите ваше имя:",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает добавление растения"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await query.answer("❌ Нет прав")
        return
    
    user_states[user_id] = {"action": "add_plant", "step": "name"}
    
    try:
        await query.edit_message_text("➕ **Добавление растения**\n\nВведите название:", parse_mode=ParseMode.MARKDOWN)
    except:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="➕ **Добавление растения**\n\nВведите название:",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_admin_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает брони"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await query.answer("❌ Нет прав")
        return
    
    bookings = load_bookings()
    
    if not bookings:
        text = "📋 **Активных броней нет**"
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_catalog")]]
    else:
        text = "📋 **АКТИВНЫЕ БРОНИ:**\n\n"
        keyboard = []
        
        for plant_id, booking in bookings.items():
            text += f"🪴 **{booking['plant_name']}**\n"
            text += f"👤 {booking['user_name']}\n"
            text += f"📱 {booking['user_phone']}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✅ Подтвердить {booking['plant_name'][:15]}...", callback_data=f"confirm_{plant_id}"),
                InlineKeyboardButton(f"❌ Отклонить", callback_data=f"reject_{plant_id}")
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_catalog")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения (для состояний)"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    # Обработка добавления растения
    if state["action"] == "add_plant":
        if state["step"] == "name":
            state["name"] = text
            state["step"] = "price"
            await update.message.reply_text("💰 Введите цену:")
            
        elif state["step"] == "price":
            state["price"] = text
            state["step"] = "description"
            await update.message.reply_text("📝 Введите описание:")
            
        elif state["step"] == "description":
            state["description"] = text
            
            # Сохраняем растение
            plants = load_plants()
            plant_id = f"plant_{len(plants) + 1}_{int(datetime.now().timestamp())}"
            
            plants[plant_id] = {
                "name": state["name"],
                "price": state["price"],
                "description": state["description"],
                "created_at": datetime.now().isoformat()
            }
            
            save_plants(plants)
            del user_states[user_id]
            
            await update.message.reply_text(
                f"✅ **Растение добавлено!**\n\n🪴 {state['name']}\n💰 {state['price']}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Обработка бронирования
    elif state["action"] == "booking":
        if state["step"] == "name":
            state["user_name"] = text
            state["step"] = "phone"
            await update.message.reply_text("📱 Введите телефон:")
            
        elif state["step"] == "phone":
            state["user_phone"] = text
            state["step"] = "comment"
            await update.message.reply_text("💬 Комментарий (или напишите 'нет'):")
            
        elif state["step"] == "comment":
            comment = text if text.lower() != "нет" else ""
            plant_id = state["plant_id"]
            
            # Сохраняем бронь
            plants = load_plants()
            bookings = load_bookings()
            
            if plant_id in bookings:
                await update.message.reply_text("😔 Растение уже забронировано!")
                del user_states[user_id]
                return
            
            bookings[plant_id] = {
                "plant_name": plants[plant_id]["name"],
                "plant_price": plants[plant_id]["price"],
                "user_id": user_id,
                "user_name": state["user_name"],
                "user_phone": state["user_phone"],
                "comment": comment,
                "created_at": datetime.now().isoformat()
            }
            
            save_bookings(bookings)
            del user_states[user_id]
            
            # Уведомляем пользователя
            await update.message.reply_text(
                f"✅ **Заявка отправлена!**\n\n🪴 {plants[plant_id]['name']}\n👤 {state['user_name']}\n📱 {state['user_phone']}\n\nАдминистратор свяжется с вами!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Уведомляем админов
            admin_text = f"🔔 **НОВАЯ БРОНЬ**\n\n🪴 {plants[plant_id]['name']}\n👤 {state['user_name']}\n📱 {state['user_phone']}\n💬 {comment or 'нет'}"
            
            for admin_id in ADMIN_IDS:
                if admin_id > 0:
                    try:
                        await context.bot.send_message(admin_id, admin_text, parse_mode=ParseMode.MARKDOWN)
                    except:
                        pass

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все callback кнопки"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_catalog":
        await show_catalog(update, context)
    
    elif data.startswith("plant_"):
        plant_id = data.replace("plant_", "")
        await show_plant(update, context, plant_id)
    
    elif data.startswith("book_"):
        plant_id = data.replace("book_", "")
        await handle_booking_button(update, context, plant_id)
    
    elif data == "admin_add":
        await handle_admin_add(update, context)
    
    elif data == "admin_bookings":
        await handle_admin_bookings(update, context)
    
    elif data.startswith("confirm_"):
        plant_id = data.replace("confirm_", "")
        await confirm_booking(update, context, plant_id)
    
    elif data.startswith("reject_"):
        plant_id = data.replace("reject_", "")
        await reject_booking(update, context, plant_id)
    
    elif data.startswith("delete_"):
        plant_id = data.replace("delete_", "")
        await delete_plant(update, context, plant_id)

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, plant_id: str):
    """Подтверждает бронь"""
    if not is_admin(update.effective_user.id):
        return
    
    bookings = load_bookings()
    if plant_id not in bookings:
        await update.callback_query.edit_message_text("❌ Бронь не найдена")
        return
    
    booking = bookings[plant_id]
    
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            booking["user_id"],
            f"✅ **БРОНЬ ПОДТВЕРЖДЕНА!**\n\n🪴 {booking['plant_name']}\n\nОжидаем вас в магазине!",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass
    
    await update.callback_query.edit_message_text(
        f"✅ Бронь подтверждена!\n\n🪴 {booking['plant_name']}\n👤 {booking['user_name']}\n\nКлиент уведомлен."
    )

async def reject_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, plant_id: str):
    """Отклоняет бронь"""
    if not is_admin(update.effective_user.id):
        return
    
    bookings = load_bookings()
    if plant_id not in bookings:
        await update.callback_query.edit_message_text("❌ Бронь не найдена")
        return
    
    booking = bookings[plant_id]
    del bookings[plant_id]
    save_bookings(bookings)
    
    # Уведомляем клиента
    try:
        await context.bot.send_message(
            booking["user_id"],
            f"😔 К сожалению, ваша бронь отклонена\n\n🪴 {booking['plant_name']}\n\nПосмотрите другие растения в каталоге.",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass
    
    await update.callback_query.edit_message_text(
        f"❌ Бронь отклонена\n\n🪴 {booking['plant_name']}\n👤 {booking['user_name']}\n\nКлиент уведомлен."
    )

async def delete_plant(update: Update, context: ContextTypes.DEFAULT_TYPE, plant_id: str):
    """Удаляет растение"""
    if not is_admin(update.effective_user.id):
        return
    
    plants = load_plants()
    bookings = load_bookings()
    
    if plant_id not in plants:
        await update.callback_query.edit_message_text("❌ Растение не найдено")
        return
    
    if plant_id in bookings:
        await update.callback_query.edit_message_text("❌ Нельзя удалить - есть активная бронь!")
        return
    
    plant_name = plants[plant_id]["name"]
    del plants[plant_id]
    save_plants(plants)
    
    await update.callback_query.edit_message_text(f"✅ Растение '{plant_name}' удалено")

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Простые обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", show_catalog))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🤖 Простой бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
