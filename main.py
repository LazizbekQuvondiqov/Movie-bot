import telebot
from telebot import types
import logging
import time
import os
from datetime import datetime
# ...
from broadcast_manager import BroadcastManager
from tmdb_handler import TMDBHandler
from favorites_manager import FavoritesManager # <<< YANGI QATOR

# --- Konfiguratsiya va Managerlarni import qilish ---
from config import (
    BOT_TOKEN, PRIVATE_CHANNEL_ID, ADMIN_CHAT_ID, BOT_USERNAME,
    START_MESSAGE, MOVIE_NOT_FOUND_FOR_USER, MEMBERSHIP_REQUIRED_MESSAGE,
    KEYBOARD_TEXTS, ADMIN_COMMANDS, PAYMENT_INSTRUCTION_MESSAGE, PREMIUM_SUCCESS_MESSAGE
)
from database import init_db, Payment # Ma'lumotlar bazasini ishga tushirish # Ma'lumotlar bazasini ishga tushirish
from movie_manager import MovieManager
from user_manager import UserManager
from channel_manager import ChannelManager
from payment_manager import PaymentManager
from broadcast_manager import BroadcastManager
from tmdb_handler import TMDBHandler

# --- Konfiguratsiyani tekshirish ---
def validate_config():
    if not BOT_TOKEN:
        print("❌ XATO: BOT_TOKEN muhit o'zgaruvchisi topilmadi!")
        return False
    if not ADMIN_CHAT_ID:
        print("❌ XATO: ADMIN_CHAT_ID muhit o'zgaruvchisi topilmadi!")
        return False
    # PRIVATE_CHANNEL_ID ham endi majburiy
    if not PRIVATE_CHANNEL_ID or PRIVATE_CHANNEL_ID == 0:
        print("❌ XATO: PRIVATE_CHANNEL_ID muhit o'zgaruvchisi topilmadi yoki 0 ga teng!")
        return False
    print("✅ Konfiguratsiya muvaffaqiyatli tekshirildi!")
    return True

# Konfiguratsiya tekshirish
if not validate_config():
    exit(1)

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot va global o'zgaruvchilar
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
try:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_CHAT_ID.split(',')]
    print(f"✅ Admin ID lar yuklandi: {ADMIN_IDS}")
except (ValueError, AttributeError):
    ADMIN_IDS = []
    print("❌ ADMIN_CHAT_ID noto'g'ri formatda yoki mavjud emas!")
    if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == "0":
        print("Dastur ADMIN_CHAT_ID sozlanmagani uchun to'xtatildi!")
        exit(1)

user_states = {}       # Foydalanuvchi holatlarini saqlash uchun
temp_movie_data = {}   # Kino qo'shish jarayonidagi vaqtinchalik ma'lumotlar

# Manager obyektlari (UserManager endi payment_managerga bog'liq EMAS)
movie_manager = MovieManager()
user_manager = UserManager()
channel_manager = ChannelManager()
payment_manager = PaymentManager()
broadcast_manager = BroadcastManager()
tmdb_handler = TMDBHandler()
favorites_manager = FavoritesManager() # <<< YANGI QATOR

DEFAULT_POSTER_URL = "https://static6.tgstat.ru/channels/_0/e7/e784ac572ebd86f1e52232e1697a8c81.jpg"
def is_user_member(user_id):
    """Foydalanuvchi kanalga a'zo yoki premium ekanligini tekshirish"""
    try:
        if payment_manager.is_premium_user(user_id):
            return True
        if not channel_manager.is_membership_required():
            return True

        channels = channel_manager.get_channel_list_for_check()
        if not channels:
            return True

        for channel in channels:
            try:
                member = bot.get_chat_member(f"@{channel.username}", user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            except Exception:
                logger.warning(f"Kanal a'zoligini tekshirib bo'lmadi: @{channel.username}")
                continue
        return True
    except Exception as e:
        logger.error(f"A'zolik tekshirishda umumiy xatolik: {e}")
        return False

def get_subscription_keyboard():
    """Majburiy obuna klaviaturasi"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    channels = channel_manager.get_channel_list_for_check()
    for channel in channels:
        keyboard.add(types.InlineKeyboardButton(f"📢 {channel.name}", url=channel.url))
    keyboard.add(types.InlineKeyboardButton(KEYBOARD_TEXTS['check_subscription'], callback_data='check_subscription'))
    prices = payment_manager.get_prices()
    keyboard.add(types.InlineKeyboardButton(f"💎 Premium ({prices['week']:,} so'm/hafta)", callback_data='show_premium'))
    return keyboard

def get_main_keyboard(user_id):
    """Asosiy menyu klaviaturasi"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton(KEYBOARD_TEXTS['search']),
        types.KeyboardButton(KEYBOARD_TEXTS['genres'])
    )
    keyboard.add(
        types.KeyboardButton(KEYBOARD_TEXTS['top_movies']),
        types.KeyboardButton(KEYBOARD_TEXTS['latest_movies'])
    )
    # <<< YANGI QATORLAR SHU YERDA >>>
    favorites_btn = types.KeyboardButton("❤️ Tanlanganlarim")
    premium_btn = types.KeyboardButton(KEYBOARD_TEXTS['premium'] + (" ✅" if payment_manager.is_premium_user(user_id) else ""))
    keyboard.add(favorites_btn, premium_btn) # Premium bilan bir qatorda
    # <<< O'ZGARISH TUGADI >>>

    if user_id in ADMIN_IDS:
        keyboard.add(types.KeyboardButton(KEYBOARD_TEXTS['admin']))
    return keyboard
def get_admin_keyboard():
    """Admin paneli klaviaturasi"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    commands = list(ADMIN_COMMANDS.values())
    for i in range(0, len(commands), 2):
        row = commands[i:i+2]
        keyboard.add(*[types.KeyboardButton(text) for text in row])
    keyboard.add(types.KeyboardButton(KEYBOARD_TEXTS['back']))
    return keyboard

def safe_send_message(chat_id, text, **kwargs):
    """Xabar yuborishda xatolik handle qilish (o'zgarmagan)"""
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Xabar yuborishda xatolik (chat_id: {chat_id}): {e}")
    return None

def safe_edit_message(chat_id, message_id, text, **kwargs):
    """Xabarni tahrirlashda xatolik handle qilish (o'zgarmagan)"""
    try:
        return bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except Exception as e:
        logger.error(f"Xabarni tahrirlashda xatolik: {e}")
    return None

def generate_movie_caption(movie):
    """Film uchun caption yaratish (Movie obyektidan)"""
    caption = f"🎬 <b>{movie.title}</b>"
    if movie.original_title and movie.original_title.lower() != movie.title.lower():
        caption += f" ({movie.original_title})"
    caption += f"\n➖➖➖➖➖➖➖➖➖➖\n"
    if movie.countries:
        caption += f"🌍 Davlat: {movie.countries}\n"
    if movie.genres:
        caption += f"🎭 Janr: {' '.join(['#' + g.strip().replace(' ', '') for g in movie.genres.split(',')])}\n"
    if movie.year:
        caption += f"📆 Yil: {movie.year}\n"
    if movie.rating and movie.rating > 0:
        caption += f"⭐ Reyting: {movie.rating}\n"
    caption += f"\n🔢 Kod: {movie.id}\n👁 Ko'rishlar: {movie.views}\n\n✅ @{BOT_USERNAME.replace('@','')} | Filmlar olami 🍿"
    return caption

# Eski send_movie funksiyasini O'CHIRIB, buni qo'ying

def send_movie(chat_id, movie_id):
    """Film yuborish logikasi (Tanlanganlar tugmasi bilan)"""
    try:
        # Foydalanuvchi mavjudligini tekshirish va aktivligini yangilash
        # Biz user_manager.add_user() ni ishlatmaymiz, chunki u keraksiz yangilanishlar qilishi mumkin.
        # Buning o'rniga, user_managerga yangi, sodda funksiya qo'shishimiz mumkin, lekin hozircha bu shart emas.
        # Agar foydalanuvchi biror harakat qilsa, u allaqachon bazada bo'ladi.

        # -1 ID maxsus holat, majburiy a'zolik xabarini chiqarish uchun
        if movie_id == -1:
             prices = payment_manager.get_prices()
             text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 {ch.name}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
             )
             bot.send_message(chat_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
             return

        if not is_user_member(chat_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 {ch.name}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            bot.send_message(chat_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return

        movie = movie_manager.get_movie(movie_id)
        if not movie:
            bot.send_message(chat_id, MOVIE_NOT_FOUND_FOR_USER.format(username=BOT_USERNAME.replace('@', '')), parse_mode='HTML')
            return

        # Ko'rishlar sonini yangilash
        new_views = movie_manager.update_views(movie_id)
        movie.views = new_views # Obyektni ham yangilab qo'yamiz
        user_manager.increment_movie_watch(chat_id)

        # Caption va tugmalarni tayyorlash
        caption = generate_movie_caption(movie)

        # <<< TUGMALAR BLOKI SHU YERDA YANGILANDI >>>
        is_favorite = favorites_manager.is_in_favorites(chat_id, movie_id)
        favorite_text = "💔 Sevimlilardan olib tashlash" if is_favorite else "❤️ Sevimlilarga qo'shish"

        keyboard = types.InlineKeyboardMarkup(row_width=2) # row_width=2 qildik

        # Birinchi qator: Sevimlilar tugmasi
        keyboard.add(types.InlineKeyboardButton(favorite_text, callback_data=f"fav_{movie_id}"))

        # Ikkinchi qator: Ulashish va Qidirish tugmalari
        keyboard.add(
            types.InlineKeyboardButton("↪️ Ulashish", switch_inline_query=movie.title),
            types.InlineKeyboardButton("🔎 Boshqa kinolar", switch_inline_query_current_chat="")
        )
        # <<< O'ZGARISH TUGADI >>>

        bot.send_video(chat_id, movie.file_id, caption=caption, parse_mode='HTML', reply_markup=keyboard, protect_content=True)
        logger.info(f"Film yuborildi: ID {movie_id}, Chat ID {chat_id}")

    except Exception as e:
        logger.error(f"Video yuborishda xatolik (movie_id: {movie_id}): {e}", exc_info=True)
        bot.send_message(chat_id, "❌ Video yuborishda kutilmagan xatolik yuz berdi.")

def send_broadcast_message(user_id, from_chat_id, message_id, reply_markup=None):
    """Universal ommaviy xabar yuborish funksiyasi"""
    try:
        bot.copy_message(user_id, from_chat_id, message_id, reply_markup=reply_markup)
        return True
    except telebot.apihelper.ApiTelegramException as e:
        if "bot was blocked by the user" in e.description:
            logger.warning(f"Foydalanuvchi {user_id} botni bloklagan.")
            # Foydalanuvchini ban qilish yoki nofaol deb belgilash mumkin
            # user_manager.ban_user(user_id, bot.get_me().id) # Misol uchun ban qilish
        else:
            logger.error(f"Xabar yuborishda xatolik (foydalanuvchi: {user_id}): {e}")
        return False
    except Exception as e:
        logger.error(f"Noma'lum xatolik (foydalanuvchi: {user_id}): {e}")
        return False

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'], func=lambda msg: user_states.get(msg.from_user.id) == 'broadcast_message')
def handle_broadcast_content(message):
    """Ommaviy xabar uchun kontentni qabul qilish va yuborishni boshlash"""
    admin_id = message.from_user.id
    try:
        # Premium bo'lmagan foydalanuvchilarni olish
        all_users = user_manager.get_all_user_ids()
        non_premium_users = [uid for uid in all_users if not payment_manager.is_premium_user(uid)]

        if not non_premium_users:
            bot.send_message(admin_id, "❌ Xabar yuborish uchun (premium bo'lmagan) foydalanuvchilar topilmadi.")
            user_states.pop(admin_id, None)
            return

        # Broadcastni boshlash
        broadcast_id = broadcast_manager.start_broadcast(bot, non_premium_users, message, admin_id)
        if broadcast_id:
             bot.send_message(admin_id, f"✅ Ommaviy xabar yuborish boshlandi!\nJami: {len(non_premium_users)} ta foydalanuvchi.\nID: `{broadcast_id}`", parse_mode="Markdown")
        else:
             bot.send_message(admin_id, "❌ Ommaviy xabarni boshlashda xatolik yuz berdi.")
    except Exception as e:
        logger.error(f"Ommaviy xabar yuborishda umumiy xatolik: {e}")
        bot.send_message(admin_id, "❌ Kutilmagan xatolik yuz berdi.")
    finally:
        user_states.pop(admin_id, None)

@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        user_manager.add_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)

        if user_manager.is_banned(user_id):
            bot.send_message(user_id, "❌ Siz botdan foydalanish uchun bloklangansiz.")
            return

        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            send_movie(user_id, int(parts[1]))
            return

        bot.send_message(user_id, START_MESSAGE, reply_markup=get_main_keyboard(user_id), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Start komandasi xatolik: {e}")

@bot.message_handler(commands=['cancel'], func=lambda msg: msg.from_user.id in ADMIN_IDS)
def cancel_command(message):
    """Admin holatlarini bekor qilish"""
    admin_id = message.from_user.id
    if admin_id in user_states:
        state = user_states.pop(admin_id, None)
        if state == 'adding_video':
             bot.send_message(admin_id, "✅ Kino qo'shish rejimi to'xtatildi.", reply_markup=get_admin_keyboard())
        else:
             bot.send_message(admin_id, "✅ Jarayon bekor qilindi.", reply_markup=get_admin_keyboard())
        temp_movie_data.clear()
    else:
        bot.send_message(admin_id, "Bekor qilinadigan faol jarayon yo'q.")
@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['search'])
def search_request(message):
    try:
        user_id = message.from_user.id
        user_manager.add_user(user_id)
        if not is_user_member(user_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 {ch.name}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            bot.send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return

        text = "Kinoni topish uchun uning nomini yoki kino kodini yozing.\n\nYoki ayrim kinolarni ko'rish uchun quyidagi tugmani bosing:"
        keyboard = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("🔎 Barcha kinolarni ko'rish", switch_inline_query_current_chat="")
        ]])
        bot.send_message(user_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Qidiruv so'rovi xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription(call):
    try:
        user_id = call.from_user.id
        if is_user_member(user_id):
            bot.answer_callback_query(call.id, "✅ Muvaffaqiyatli! Botdan foydalanishingiz mumkin.")
            # Xabarni o'chirib, asosiy menyuni yuboramiz
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(user_id, "Bosh menyu:", reply_markup=get_main_keyboard(user_id))
        else:
            bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    except Exception as e:
        logger.error(f"Obuna tekshirishda xatolik: {e}")

@bot.inline_handler(func=lambda query: True)
def inline_search(query):
    try:
        user_id = query.from_user.id
        if not is_user_member(user_id):
            # Bu qismni qisqartiramiz, chunki foydalanuvchi botga o'tib, baribir /start bosadi
            bot.answer_inline_query(query.id, [], switch_pm_text="Botdan foydalanish uchun kanallarga obuna bo'ling", switch_pm_parameter="subscribe")
            return

        search_query = query.query.strip().lower()
        movies = movie_manager.search_movies(search_query) # Bu endi Movie obyektlari ro'yxatini qaytaradi

        results = []
        if not movies:
            # Film topilmaganda ham switch_pm_text taklif qilamiz
            bot.answer_inline_query(query.id, [], switch_pm_text=f"'{search_query}' topilmadi. Boshqa nom bilan qidiring.", switch_pm_parameter="search")
            return

        for movie in movies[:50]: # Telegram inline uchun limit 50 ta
            description = f"⭐ {movie.rating or 'N/A'} | 📅 {movie.year or 'N/A'} | 👁 {movie.views or 0}"
            result = types.InlineQueryResultArticle(
                id=str(movie.id),
                title=movie.title,
                description=description,
                thumbnail_url=movie.poster_url or DEFAULT_POSTER_URL,
                input_message_content=types.InputTextMessageContent(f"/start {movie.id}")
            )
            results.append(result)

        bot.answer_inline_query(query.id, results, cache_time=10) # Cache vaqtini qisqartiramiz
    except Exception as e:
        logger.error(f"Inline qidiruvda kutilmagan xatolik: {e}", exc_info=True)



def generate_movie_list_text(movies, list_title):
    """Kino ro'yxatini matn ko'rinishida formatlash (Movie obyektlari uchun)"""
    if not movies:
        return f"Hozircha {list_title.lower()} topilmadi."

    text = f"<b>{list_title}:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += f"<b>{i}. {movie.title}</b> ({movie.year or 'N/A'}) - ⭐ {movie.rating or 'N/A'}\n"
        text += f"Kinoni ko'rish uchun yuboring: <code>{movie.id}</code>\n\n"
    return text

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['top_movies'])
def handle_top_movies(message):
    """Eng ommabop kinolar ro'yxatini yuborish"""
    user_id = message.from_user.id
    if not is_user_member(user_id):
        send_movie(user_id, -1) # Bu membership xabarini chiqaradi
        return

    bot.send_chat_action(user_id, 'typing')
    top_movies = movie_manager.get_top_movies(limit=10)
    text = generate_movie_list_text(top_movies, "🏆 Eng Ommabop 10 Kino")
    bot.send_message(user_id, text, parse_mode='HTML')

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['latest_movies'])
def handle_latest_movies(message):
    """Eng so'nggi qo'shilgan kinolar ro'yxatini yuborish"""
    user_id = message.from_user.id
    if not is_user_member(user_id):
        send_movie(user_id, -1)
        return

    bot.send_chat_action(user_id, 'typing')
    latest_movies = movie_manager.get_latest_movies(limit=10)
    text = generate_movie_list_text(latest_movies, "✨ Eng So'nggi Qo'shilgan Kinolar")
    bot.send_message(user_id, text, parse_mode='HTML')

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['genres'])
def handle_genres(message):
    """Janrlar menyusini ko'rsatish"""
    user_id = message.from_user.id
    if not is_user_member(user_id):
        send_movie(user_id, -1)
        return

    bot.send_chat_action(user_id, 'typing')
    genres = movie_manager.get_all_genres()
    if not genres:
        return bot.send_message(user_id, "Hozircha janrlar mavjud emas.")

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(g, callback_data=f"genre_{g}") for g in genres]
    keyboard.add(*buttons)
    bot.send_message(user_id, "🎭 Kerakli janrni tanlang:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('genre_'))
def handle_genre_selection(call):
    """Tanlangan janr bo'yicha kinolarni ko'rsatish"""
    try:
        bot.answer_callback_query(call.id)
        selected_genre = call.data.split('_', 1)[1]

        bot.send_chat_action(call.message.chat.id, 'typing')
        genre_movies = movie_manager.get_movies_by_genre(selected_genre, limit=10)
        text = generate_movie_list_text(genre_movies, f"🎭 {selected_genre} Janridagi Kinolar (Top 10)")

        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Janr bo'yicha kinolarni ko'rsatishda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text in [KEYBOARD_TEXTS['premium'], KEYBOARD_TEXTS['premium'] + " ✅"])
def handle_premium(message):
    try:
        user_id = message.from_user.id
        user_manager.add_user(user_id)

        premium_info = payment_manager.get_premium_info(user_id)
        if premium_info and premium_info.is_active:
            text = f"""✅ <b>Premium obuna faol!</b>

📅 <b>Boshlangan sana:</b> {premium_info.start_date.strftime('%d.%m.%Y')}
⏰ <b>Tugash sanasi:</b> {premium_info.expire_date.strftime('%d.%m.%Y')}
💎 <b>Reja:</b> {premium_info.plan_type.title()}

🎯 Siz kanallarga a'zo bo'lish majburiyatisiz botdan foydalanishingiz mumkin."""
            bot.send_message(user_id, text, parse_mode='HTML')
        else:
            prices = payment_manager.get_prices()
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(types.InlineKeyboardButton(f"📅 1 hafta - {prices['week']:,} so'm", callback_data='premium_week'))
            keyboard.add(types.InlineKeyboardButton(f"📅 1 oy - {prices['month']:,} so'm", callback_data='premium_month'))
            keyboard.add(types.InlineKeyboardButton(f"📅 1 yil - {prices['year']:,} so'm", callback_data='premium_year'))

            text = f"""💎 <b>Premium Obuna</b>

🎯 <b>Imkoniyatlar:</b>
• 🚫 Kanallarga a'zo bo'lish majburiyati yo'q
• 🎯 Reklamasiz foydalanish
• ⚡ Tezkor qidiruv va yuklash

💰 <b>Narxlar:</b>"""
            bot.send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Premium handle xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.from_user.id in ADMIN_IDS and msg.text in list(KEYBOARD_TEXTS.values()) + list(ADMIN_COMMANDS.values()))
def handle_admin_keyboard(message):
    """Admin klaviatura handleri"""
    user_id = message.from_user.id
    text = message.text

    if text == KEYBOARD_TEXTS['admin']:
        bot.send_message(user_id, "⚙️ Admin Panel", reply_markup=get_admin_keyboard())
    elif text == KEYBOARD_TEXTS['back']:
        user_states.pop(user_id, None)
        bot.send_message(user_id, "🏠 Asosiy menyu", reply_markup=get_main_keyboard(user_id))

    elif text == ADMIN_COMMANDS['add_video']:
        bot.send_message(user_id, "📹 Qo'shmoqchi bo'lgan video faylni o'zbekcha sarlavha (caption) bilan yuboring.\n\n"
                                  "💡 Kino qo'shish rejimini to'xtatish uchun /cancel buyrug'ini yuboring.")
        user_states[user_id] = 'adding_video'

    elif text == ADMIN_COMMANDS['delete_video']:
        bot.send_message(user_id, "🗑 O'chirmoqchi bo'lgan kinoning ID raqamini yuboring:")
        user_states[user_id] = 'delete_video'

    elif text == ADMIN_COMMANDS['broadcast']:
        bot.send_message(user_id, "📢 Ommaviy xabar uchun postni menga yuboring (forward qiling).")
        user_states[user_id] = 'broadcast_message'

    elif text == ADMIN_COMMANDS['stats']:
        try:
            movie_stats = movie_manager.get_stats()
            user_stats = user_manager.get_user_stats()
            payment_stats = payment_manager.get_payment_stats()

            stats_text = f"""📊 <b>Bot Statistikasi</b>\n\n""" \
                         f"🎬 <b>Filmlar:</b>\n" \
                         f"  • Jami filmlar: {movie_stats['total_movies']}\n" \
                         f"  • Jami ko'rishlar: {movie_stats['total_views']}\n\n" \
                         f"👥 <b>Foydalanuvchilar:</b>\n" \
                         f"  • Jami: {user_stats['total_users']}\n" \
                         f"  • Faol: {user_stats['active_users']}\n" \
                         f"  • Premium: {payment_stats['active_premium_users']}\n\n" \
                         f"💰 <b>To'lovlar:</b>\n" \
                         f"  • Jami: {payment_stats['total_payments']}\n" \
                         f"  • Kutilmoqda: {payment_stats['pending_payments']}\n" \
                         f"  • Jami daromad: {payment_stats['total_earned']:,} so'm"
            bot.send_message(user_id, stats_text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Statistika olishda xatolik: {e}")
            bot.send_message(user_id, "❌ Statistikani olishda xatolik yuz berdi.")

    elif text == ADMIN_COMMANDS['manage_channels']:
        text = generate_channels_list_text()
        keyboard = get_channels_management_keyboard()
        bot.send_message(user_id, text, reply_markup=keyboard, parse_mode='HTML')

    elif text == ADMIN_COMMANDS['premium_settings']:
        try:
            prices = payment_manager.get_prices()
            card_info = payment_manager.get_card_info()
            text = f"""💎 <b>Premium sozlamalari</b>\n\n💰 <b>Joriy narxlar:</b>\n• 1 hafta: {prices['week']:,} so'm\n• 1 oy: {prices['month']:,} so'm\n• 1 yil: {prices['year']:,} so'm\n\n💳 <b>To'lov ma'lumotlari:</b>\n• Karta: {card_info['card_number']}\n• Egasi: {card_info['card_holder']}\n\n💡 O'zgartirish uchun tugmalardan foydalaning:"""
            keyboard = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("💰 Narxlarni o'zgartirish", callback_data='change_prices')],
                [types.InlineKeyboardButton("💳 Karta ma'lumotlarini o'zgartirish", callback_data='change_card')]
            ])
            bot.send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Premium sozlamalarida xatolik: {e}")
            bot.send_message(user_id, "❌ Premium sozlamalarni yuklashda xatolik.")

    elif text == ADMIN_COMMANDS['payment_requests']:
        pending_payments = payment_manager.get_pending_payments()
        if not pending_payments:
            bot.send_message(user_id, "💳 Kutilayotgan to'lov so'rovlari yo'q.")
        else:
            for payment in pending_payments:
                user = user_manager.get_user(payment.user_id)
                username_display = f"@{user.username}" if user and user.username else f"ID: {payment.user_id}"

                text = f"""💳 <b>Yangi to'lov so'rovi!</b>

👤 <b>Foydalanuvchi:</b> {username_display}
💰 <b>Summa:</b> {payment.amount:,} so'm ({payment.plan_type})
📅 <b>Sana:</b> {payment.created_at.strftime('%Y-%m-%d %H:%M')}
🆔 <b>Payment ID:</b> <code>{payment.id}</code>"""

                keyboard = types.InlineKeyboardMarkup([[
                    types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_payment_{payment.id}"),
                    types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment.id}")
                ]])

                # Chekni kanaldan link orqali yuborish
                bot.send_message(user_id, f"{text}\n\n<a href='{payment.check_message_link}'>🧾 Chekni ko'rish</a>", parse_mode='HTML', reply_markup=keyboard)
@bot.message_handler(content_types=['video'], func=lambda msg: user_states.get(msg.from_user.id) == 'adding_video')
def handle_video_upload(message):
    admin_id = message.from_user.id
    try:
        uzbek_title, _, _ = tmdb_handler.parse_caption(message.caption or '')
        if not uzbek_title:
            bot.send_message(admin_id, "❌ Video sarlavhasi (caption) bo'sh. Iltimos, film nomini kiriting.")
            return

        msg_to_edit = bot.send_message(admin_id, f"⏳ '{uzbek_title}' ma'lumotlari qidirilmoqda...")

        tmdb_results = tmdb_handler.search_movie(uzbek_title)

        # <<< MUHIM: Videoni avval kanalga yuborish >>>
        try:
            channel_message = bot.forward_message(PRIVATE_CHANNEL_ID, admin_id, message.message_id)
            channel_file_id = channel_message.video.file_id
            logger.info(f"Video kanalga yuborildi. Yangi file_id: {channel_file_id}")
        except Exception as e:
            logger.error(f"Videoni kanalga yuborishda xatolik: {e}")
            bot.edit_message_text("❌ Videoni maxfiy kanalga yuborib bo'lmadi. Kanal sozlamalarini tekshiring.", admin_id, msg_to_edit.message_id)
            return

        if not tmdb_results:
            logger.warning(f"'{uzbek_title}' uchun TMDB'dan natija topilmadi. Ma'lumotlarsiz qo'shilmoqda.")
            movie_data = {
                'file_id': channel_file_id,
                'title': uzbek_title,
                'poster_url': DEFAULT_POSTER_URL
            }
            new_id = movie_manager.add_movie(movie_data)
            if new_id:
                success_text = f"✅ Film TMDB ma'lumotlarisiz qo'shildi!\n\n🆔 Kino kodi: {new_id}\n🎬 Nomi: {uzbek_title}\n\n" \
                               f"💡 Keyingi kinoni yuboring yoki /cancel buyrug'i bilan to'xtating."
                bot.edit_message_text(success_text, admin_id, msg_to_edit.message_id)
            else:
                bot.edit_message_text("❌ Filmni bazaga saqlashda xatolik.", admin_id, msg_to_edit.message_id)
            return

        temp_key = f"{admin_id}_{message.message_id}"
        temp_movie_data[temp_key] = {
            'file_id': channel_file_id, # <<< Kanaldagi file_id saqlanadi
            'title': uzbek_title
        }

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for movie in tmdb_results:
            year = movie.get('release_date', 'N/A')[:4] if movie.get('release_date') else 'N/A'
            btn_text = f"{movie['title']} ({year})"
            keyboard.add(types.InlineKeyboardButton(btn_text, callback_data=f"confirm_{movie['id']}_{temp_key}"))

        # Bekor qilish endi /cancel buyrug'i bilan
        bot.edit_message_text(f"👇 '{uzbek_title}' uchun topilgan natijalardan birini tanlang:", admin_id, msg_to_edit.message_id, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Video yuklashda kutilmagan xatolik: {e}", exc_info=True)
        bot.send_message(admin_id, "❌ Video qo'shishda kutilmagan xatolik yuz berdi.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def handle_tmdb_confirmation(call):
    admin_id = call.from_user.id
    try:
        bot.answer_callback_query(call.id)

        parts = call.data.split('_', 2)
        tmdb_id, temp_key = int(parts[1]), parts[2]

        movie_data = temp_movie_data.get(temp_key)
        if not movie_data:
            bot.edit_message_text("❌ Xatolik: Vaqt o'tib ketdi. Qaytadan video yuklang.", call.message.chat.id, call.message.message_id)
            return

        bot.edit_message_text("⏳ Ma'lumotlar birlashtirilmoqda...", call.message.chat.id, call.message.message_id)

        details = tmdb_handler.get_movie_details(tmdb_id)
        if not details:
            bot.edit_message_text(f"❌ TMDB'dan (ID: {tmdb_id}) ma'lumot olib bo'lmadi.", call.message.chat.id, call.message.message_id)
            return

        movie_data.update(details)

        new_id = movie_manager.add_movie(movie_data)
        if new_id:
            success_text = f"✅ Film muvaffaqiyatli qo'shildi!\n\n🆔 Kino kodi: {new_id}\n🎬 Nomi: {movie_data['title']}\n\n" \
                           f"💡 Keyingi kinoni yuboring yoki /cancel buyrug'i bilan to'xtating."
            bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id)
        else:
            bot.edit_message_text("❌ Filmni bazaga saqlashda xatolik yuz berdi.", call.message.chat.id, call.message.message_id)

    except Exception as e:
        logger.error(f"TMDB tasdiqlashda xatolik: {e}", exc_info=True)
        bot.edit_message_text("❌ Kutilmagan jiddiy xatolik yuz berdi.", call.message.chat.id, call.message.message_id)
    finally:
        # temp_key ni tozalaymiz, lekin adding_video holati qoladi
        if 'temp_key' in locals() and temp_key in temp_movie_data:
            del temp_movie_data[temp_key]

@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_') or call.data == 'show_premium')
def handle_premium_purchase(call):
    try:
        bot.answer_callback_query(call.id)

        if call.data == 'show_premium':
            prices = payment_manager.get_prices()
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(types.InlineKeyboardButton(f"📅 1 hafta - {prices['week']:,} so'm", callback_data='premium_week'))
            keyboard.add(types.InlineKeyboardButton(f"📅 1 oy - {prices['month']:,} so'm", callback_data='premium_month'))
            keyboard.add(types.InlineKeyboardButton(f"📅 1 yil - {prices['year']:,} so'm", callback_data='premium_year'))
            text = "💎 <b>Premium Obuna</b>\n\n🎯 <b>Imkoniyatlar:</b>\n• 🚫 Kanallarga a'zo bo'lish majburiyati yo'q\n• 🎯 Reklamasiz foydalanish\n\n💰 <b>Narxlar:</b>"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            return

        plan_type = call.data.replace('premium_', '')
        prices = payment_manager.get_prices()
        card_info = payment_manager.get_card_info()
        amount = prices.get(plan_type)

        if not amount:
            bot.answer_callback_query(call.id, "❌ Noto'g'ri reja!", show_alert=True)
            return

        plan_names = {'week': '1 hafta', 'month': '1 oy', 'year': '1 yil'}
        text = PAYMENT_INSTRUCTION_MESSAGE.format(
            amount=amount,
            duration=plan_names[plan_type],
            card_number=card_info['card_number'],
            card_holder=card_info['card_holder'],
            bank_name=card_info.get('bank_name', 'N/A')
        )
        keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("✅ To'lov qildim", callback_data=f"paid_{plan_type}_{amount}")]])
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Premium sotib olishda xatolik: {e}")

# Eski handle_payment_confirmation ni O'CHIRIB, buni qo'ying

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def handle_payment_confirmation(call):
    try:
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        parts = call.data.split('_')

        # Callback ma'lumotlarini tekshirish
        if len(parts) != 3:
            bot.edit_message_text("❌ Xatolik yuz berdi. Iltimos, /start buyrug'i bilan qaytadan boshlang.", call.message.chat.id, call.message.message_id)
            return

        plan_type, amount = parts[1], int(parts[2])

        # <<< MUHIM TUZATISH: State'dagi _ belgisini olib tashlaymiz >>>
        user_states[user_id] = f'paymentscreenshot_{plan_type}_{amount}'

        text = "📸 To'lov chekini rasm (screenshot) yoki PDF formatda yuboring."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
        logger.info(f"Foydalanuvchi {user_id} uchun 'paymentscreenshot' holati o'rnatildi.")

    except Exception as e:
        logger.error(f"To'lov tasdiqlashda xatolik: {e}", exc_info=True)
# Yangi tuzatilgan payment proof handler
# Eski handle_payment_proof ni O'CHIRIB, buni qo'ying

@bot.message_handler(content_types=['photo', 'document'], func=lambda msg: user_states.get(msg.from_user.id, '').startswith('paymentscreenshot_'))
def handle_payment_proof(message):
    user_id = message.from_user.id
    try:
        state = user_states.get(user_id)

        # <<< MUHIM TUZATISH: State'ni to'g'ri bo'lish >>>
        parts = state.split('_')
        if len(parts) != 3:
            bot.send_message(user_id, "❌ Sessiya buzilgan. Iltimos, /start buyrug'i bilan qaytadan boshlang.")
            return

        _, plan_type, amount_str = parts
        amount = int(amount_str)

        # Fayl ID'sini olamiz
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id

        if not file_id:
            bot.send_message(user_id, "❌ Fayl qabul qilinmadi. Iltimos, rasm yoki PDF yuboring.")
            return

        # Payment so'rovini bazada YARATAMIZ
        payment_id = payment_manager.create_payment_request(user_id, plan_type, amount, check_message_link=None)
        if not payment_id:
            bot.send_message(user_id, "❌ To'lov so'rovini yaratishda xatolik yuz berdi.")
            return

        # Adminlarga yuboriladigan xabar
        user_info = f"👤 Foydalanuvchi: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> (@{message.from_user.username or 'N/A'})"
        admin_text = f"""💳 <b>Yangi to'lov so'rovi!</b>

{user_info}
💰 <b>Summa:</b> {amount:,} so'm ({plan_type})
🆔 <b>Payment ID:</b> <code>{payment_id}</code>"""

        # Tasdiqlash/rad etish tugmalari
        keyboard = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_payment_{payment_id}"),
            types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment_id}")
        ]])

        # Chekni to'g'ridan-to'g'ri ADMINLARGA yuboramiz
        successful_sends = 0
        for admin_id_loop in ADMIN_IDS:
            try:
                bot.copy_message(admin_id_loop, user_id, message.message_id, caption=admin_text, parse_mode='HTML', reply_markup=keyboard)
                successful_sends += 1
            except Exception as e:
                logger.error(f"Adminga ({admin_id_loop}) chek yuborishda xatolik: {e}")

        if successful_sends > 0:
             bot.send_message(user_id, f"✅ To'lov cheki qabul qilindi va {successful_sends} ta adminga yuborildi!\n\n⏳ Tasdiqlanishini kuting.")
        else:
            bot.send_message(user_id, "❌ Xatolik: Chekni adminga yuborib bo'lmadi. Iltimos, keyinroq qayta urinib ko'ring.")

    except Exception as e:
        logger.error(f"To'lov isbotini qabul qilishda umumiy xatolik: {e}", exc_info=True)
        bot.send_message(user_id, "❌ Kutilmagan jiddiy xatolik yuz berdi.")
    finally:
        user_states.pop(user_id, None)
@bot.callback_query_handler(func=lambda call: call.data in ['toggle_membership', 'change_prices', 'change_card'])
def handle_admin_settings_callbacks(call):
    admin_id = call.from_user.id
    if admin_id not in ADMIN_IDS:
        return bot.answer_callback_query(call.id, "❌ Sizda ruxsat yo'q!", show_alert=True)

    try:
        bot.answer_callback_query(call.id)

        if call.data == 'toggle_membership':
            success, message = channel_manager.toggle_membership_check()
            bot.answer_callback_query(call.id, message, show_alert=True)
            # Menyuni yangilangan ma'lumotlar bilan qayta chizamiz
            text = generate_channels_list_text()
            keyboard = get_channels_management_keyboard()
            # Xatolik bo'lmasligi uchun tahrirlashdan oldin tekshiramiz
            if call.message.text != text:
                 bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            else:
                 bot.edit_message_reply_markup(admin_id, call.message.message_id, reply_markup=keyboard)

        elif call.data == 'change_prices':
            bot.edit_message_text("💰 Yangi narxlarni quyidagi formatda yuboring:\n\n`hafta,oy,yil`\n\nMasalan: `15000,40000,350000`",
                                  call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            user_states[admin_id] = 'change_prices'

        elif call.data == 'change_card':
            bot.edit_message_text("💳 Yangi karta ma'lumotlarini quyidagi formatda yuboring:\n\n`KARTA_RAQAMI,KARTA_EGASI,BANK_NOMI`\n\nMasalan: `8600...,John Doe,Uzcard`",
                                  call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            user_states[admin_id] = 'change_card'

    except Exception as e:
        logger.error(f"Admin sozlamalari callback xatoligi: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_payment_', 'reject_payment_')))
def handle_admin_payment_decision(call):
    admin_id = call.from_user.id
    if admin_id not in ADMIN_IDS:
        return bot.answer_callback_query(call.id, "❌ Sizda ruxsat yo'q!", show_alert=True)

    try:
        parts = call.data.split('_')
        action = parts[0]
        payment_id = int(parts[2])

        db = next(payment_manager.get_db())
        payment = db.query(Payment).get(payment_id)
        if not payment:
            bot.answer_callback_query(call.id, "❌ To'lov topilmadi yoki allaqachon ko'rib chiqilgan!", show_alert=True)
            bot.edit_message_caption(call.message.caption + "\n\n⚠️ <b>Xatolik:</b> To'lov topilmadi.", call.message.chat.id, call.message.message_id, parse_mode='HTML')
            return

        user_id = payment.user_id

        if action == 'approve':
            success, message = payment_manager.approve_payment(payment_id)
            if success:
                bot.answer_callback_query(call.id, "✅ To'lov tasdiqlandi!")

                premium_info = payment_manager.get_premium_info(user_id)
                user_text = PREMIUM_SUCCESS_MESSAGE.format(expire_date=premium_info.expire_date.strftime('%d.%m.%Y'))
                bot.send_message(user_id, user_text, parse_mode='HTML')

                new_caption = f"{call.message.caption}\n\n✅ <b>TASDIQLANDI</b> by @{call.from_user.username or call.from_user.first_name}"
                bot.edit_message_caption(new_caption, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=None)
            else:
                bot.answer_callback_query(call.id, f"❌ Xatolik: {message}", show_alert=True)

        else: # reject
            success, message = payment_manager.reject_payment(payment_id)
            if success:
                bot.answer_callback_query(call.id, "❌ To'lov rad etildi!")
                bot.send_message(user_id, "❌ Sizning to'lov so'rovingiz rad etildi. Agar bu xatolik deb hisoblasangiz, adminga murojaat qiling.")

                new_caption = f"{call.message.caption}\n\n❌ <b>RAD ETILDI</b> by @{call.from_user.username or call.from_user.first_name}"
                bot.edit_message_caption(new_caption, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=None)
            else:
                bot.answer_callback_query(call.id, f"❌ Xatolik: {message}", show_alert=True)

    except Exception as e:
        logger.error(f"Admin to'lov qarorida xatolik: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "Kritik xatolik yuz berdi!", show_alert=True)


# ... handle_admin_payment_decision dan keyin qo'shing ...

@bot.callback_query_handler(func=lambda call: call.data.startswith('fav_'))
def handle_toggle_favorite(call):
    """Kino ostidagi sevimlilar tugmasini bosishni boshqarish"""
    try:
        user_id = call.from_user.id
        movie_id = int(call.data.split('_')[1])

        # Sevimlilarga qo'shish/olib tashlash
        action_is_add = favorites_manager.toggle_favorite(user_id, movie_id)

        # Tugmani yangilash
        favorite_text = "💔 Olib tashlash" if action_is_add else "❤️ Sevimlilarga qo'shish"

        # Xabardagi barcha tugmalarni qayta chizamiz
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(favorite_text, callback_data=f"fav_{movie_id}"))
        # Eski ulashish va qidirish tugmalarini ham qo'shamiz
        # Bu yerda biz kino nomini bilmaymiz, shuning uchun soddaroq qilamiz
        # Yaxshiroq usul - kino nomini callback_data ga qo'shish, lekin hozircha shunday qoldiramiz
        keyboard.add(
            types.InlineKeyboardButton("↪️ Ulashish", switch_inline_query=""),
            types.InlineKeyboardButton("🔎 Boshqa kinolar", switch_inline_query_current_chat="")
        )

        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)

        alert_text = "✅ Sevimlilarga qo'shildi!" if action_is_add else "🗑️ Sevimlilardan olib tashlandi."
        bot.answer_callback_query(call.id, alert_text)

    except Exception as e:
        logger.error(f"Sevimlilarni o'zgartirishda xatolik: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")


@bot.message_handler(func=lambda msg: msg.text == "❤️ Tanlanganlarim")
def handle_show_favorites(message):
    """Sevimlilar ro'yxatini ko'rsatish"""
    user_id = message.from_user.id
    bot.send_chat_action(user_id, 'typing')

    favorite_ids = favorites_manager.get_user_favorites(user_id)

    if not favorite_ids:
        return bot.send_message(user_id, "Sizda hali sevimlilarga qo'shilgan kinolar yo'q.")

    text = "❤️ <b>Sizning tanlangan kinolaringiz:</b>\n\n"

    # Har bir kino ma'lumotini bazadan olamiz
    for i, movie_id in enumerate(favorite_ids, 1):
        movie = movie_manager.get_movie(movie_id)
        if movie:
            text += f"<b>{i}. {movie.title}</b> ({movie.year or 'N/A'})\n"
            text += f"Ko'rish uchun kod: <code>{movie.id}</code>\n\n"
        else:
            # Agar kino bazadan o'chirilgan bo'lsa
            text += f"<b>{i}.</b> <i>(Bu kino o'chirilgan)</i>\n\n"

    bot.send_message(user_id, text, parse_mode='HTML')

def get_channels_management_keyboard():
    """Kanallarni boshqarish uchun inline klaviatura"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"))
    keyboard.add(
        types.InlineKeyboardButton("🗑 O'chirish", callback_data="remove_channel_select"),
        types.InlineKeyboardButton("🔄 Holatini o'zgartirish", callback_data="toggle_channel_select")
    )
    status_text = "❌ Majburiy a'zolikni o'chirish" if channel_manager.is_membership_required() else "✅ Majburiy a'zolikni yoqish"
    keyboard.add(types.InlineKeyboardButton(status_text, callback_data="toggle_membership"))
    return keyboard

def generate_channels_list_text():
    """Kanallar ro'yxatini matn formatida yaratish"""
    channels = channel_manager.get_all_channels()
    if not channels:
        return "Hozircha majburiy kanallar yo'q."

    text = "📢 <b>Kanallar ro'yxati:</b>\n\n"
    for i, ch in enumerate(channels, 1):
        status = "✅ Faol" if ch.is_active else "❌ Nofaol"
        text += f"{i}. {ch.name} (<code>@{ch.username}</code>) - {status}\n"
    return text

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_manage_'))
def handle_channel_management_callbacks(call):
    admin_id = call.from_user.id
    if admin_id not in ADMIN_IDS: return

    try:
        parts = call.data.split('_', 3)
        action = parts[2]

        if action == 'back':
            bot.answer_callback_query(call.id)
            text = generate_channels_list_text()
            keyboard = get_channels_management_keyboard()
            bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            return

        username = parts[3]
        if action == 'delete':
            success, msg = channel_manager.remove_channel(username)
        elif action == 'toggle':
            success, msg = channel_manager.toggle_channel_status(username)
        else:
            return

        bot.answer_callback_query(call.id, text=msg, show_alert=True)
        text = generate_channels_list_text()
        keyboard = get_channels_management_keyboard()
        bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Kanalni boshqarish callback xatoligi: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ['add_channel', 'remove_channel_select', 'toggle_channel_select', 'toggle_membership'])
def handle_channel_menu_selection(call):
    admin_id = call.from_user.id
    if admin_id not in ADMIN_IDS: return

    try:
        bot.answer_callback_query(call.id)
        if call.data == 'add_channel':
            user_states[admin_id] = 'add_channel'
            bot.edit_message_text("➕ Kanal @username'ini yoki linkini yuboring.", admin_id, call.message.message_id)
            return

        if call.data == 'toggle_membership':
            success, msg = channel_manager.toggle_membership_check()
            bot.answer_callback_query(call.id, msg, show_alert=True)
            text = generate_channels_list_text()
            keyboard = get_channels_management_keyboard()
            bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            return

        channels = channel_manager.get_all_channels()
        if not channels:
            bot.answer_callback_query(call.id, "Hozircha kanallar yo'q!", show_alert=True)
            return

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        if call.data == 'remove_channel_select':
            action_word, callback_prefix = "O'chirish uchun", "ch_manage_delete_"
        else: # toggle_channel_select
            action_word, callback_prefix = "Holatini o'zgartirish uchun", "ch_manage_toggle_"

        for ch in channels:
            keyboard.add(types.InlineKeyboardButton(ch.name, callback_data=f"{callback_prefix}{ch.username}"))

        keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="ch_manage_back_"))
        bot.edit_message_text(f"👇 {action_word} kanalni tanlang:", admin_id, call.message.message_id, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Kanal menyusini tanlashda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.from_user.id in ADMIN_IDS and user_states.get(msg.from_user.id))
def handle_admin_states(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    try:
        if state == 'add_channel':
            success, msg = channel_manager.add_channel(message.text)
            bot.send_message(user_id, msg)
            if success:
                text = generate_channels_list_text()
                keyboard = get_channels_management_keyboard()
                bot.send_message(user_id, text, reply_markup=keyboard, parse_mode='HTML')
            user_states.pop(user_id, None)

        elif state == 'delete_video':
            if message.text.isdigit():
                success, msg = movie_manager.delete_movie(int(message.text))
                bot.send_message(user_id, msg)
            else:
                bot.send_message(user_id, "❌ Noto'g'ri format. Faqat raqam kiriting.")
            user_states.pop(user_id, None)

        elif state == 'find_user':
            user = user_manager.find_user(message.text)
            if user:
                is_premium = payment_manager.is_premium_user(user.user_id)
                premium_text = "✅ Ha"
                if is_premium:
                    info = payment_manager.get_premium_info(user.user_id)
                    premium_text += f" ({info.expire_date.strftime('%d.%m.%Y')} gacha)"
                else:
                    premium_text = "❌ Yo'q"

                text = f"""👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n""" \
                       f"<b>Ism:</b> {user.first_name}\n" \
                       f"<b>ID:</b> <code>{user.user_id}</code>\n" \
                       f"<b>Username:</b> @{user.username}\n" \
                       f"<b>Qo'shilgan:</b> {user.joined_date.strftime('%d.%m.%Y')}\n" \
                       f"<b>Ko'rilgan kinolar:</b> {user.movies_watched}\n" \
                       f"💎 <b>Premium:</b> {premium_text}"
                bot.send_message(user_id, text, parse_mode='HTML')
            else:
                bot.send_message(user_id, "❌ Foydalanuvchi topilmadi.")
            user_states.pop(user_id, None)

        elif state == 'change_prices':
            try:
                week, month, year = map(int, message.text.split(','))
                payment_manager.update_prices({'week': week, 'month': month, 'year': year})
                bot.send_message(user_id, "✅ Narxlar muvaffaqiyatli yangilandi!")
            except Exception:
                bot.send_message(user_id, "❌ Noto'g'ri format. Masalan: `15000,40000,350000`")
            finally:
                user_states.pop(user_id, None)

        elif state == 'change_card':
            try:
                number, holder, bank = map(str.strip, message.text.split(','))
                payment_manager.update_card_info({'card_number': number, 'card_holder': holder, 'bank_name': bank})
                bot.send_message(user_id, "✅ Karta ma'lumotlari yangilandi!")
            except Exception:
                bot.send_message(user_id, "❌ Noto'g'ri format. Masalan: `8600...,John Doe,Uzcard`")
            finally:
                user_states.pop(user_id, None)

    except Exception as e:
        logger.error(f"Admin state ({state}) xatoligi: {e}")
        bot.send_message(user_id, "❌ Buyruqni bajarishda xatolik yuz berdi.")
        user_states.pop(user_id, None)

@bot.message_handler(func=lambda msg: msg.text and msg.text.isdigit())
def handle_id_message(message):
    """ID bo'yicha film topish"""
    # Agar admin biror state da bo'lsa, bu funksiya ishlamaydi
    if user_states.get(message.from_user.id):
        return
    send_movie(message.chat.id, int(message.text))

@bot.message_handler(content_types=['text'])
def handle_text_message(message):
    """Barcha boshqa matnli xabarlar (qidiruv uchun)"""
    if user_states.get(message.from_user.id):
        return

    user_id = message.from_user.id
    user_manager.add_user(user_id)
    if user_manager.is_banned(user_id):
        return

    if not is_user_member(user_id):
        prices = payment_manager.get_prices()
        text = MEMBERSHIP_REQUIRED_MESSAGE.format(
            channels="\n".join([f"📢 {ch.name}" for ch in channel_manager.get_channel_list_for_check()]),
            week_price=prices['week'],
            month_price=prices['month'],
            year_price=prices['year']
        )
        bot.send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
        return

    keyboard = types.InlineKeyboardMarkup([[
        types.InlineKeyboardButton(f"🔎 '{message.text}' bo'yicha qidirish", switch_inline_query_current_chat=message.text)
    ]])
    bot.send_message(user_id, f"Natijalarni ko'rish uchun tugmani bosing:", reply_markup=keyboard)

def main():
    try:
        logger.info("Ma'lumotlar bazasi jadvallari tekshirilmoqda...")
        init_db() # Dastur ishga tushganda jadvallarni yaratadi

        for admin_id in ADMIN_IDS:
             try:
                 bot.send_message(admin_id, "🤖 Bot muvaffaqiyatli ishga tushirildi!")
             except Exception as e:
                 logger.warning(f"Adminga ({admin_id}) xabar yuborib bo'lmadi: {e}")

        logger.info("Bot ishlayapti...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.critical(f"Botning ishlashida jiddiy xatolik: {e}", exc_info=True)
        time.sleep(15)
        # main() # Avtomatik qayta ishga tushirishni vaqtincha o'chiramiz, xatoni ko'rish uchun

if __name__ == '__main__':
    main()
