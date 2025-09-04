import telebot
from telebot import types
import logging
import time
import os
from config import (
    BOT_TOKEN, PRIVATE_CHANNEL_ID, ADMIN_CHAT_ID, BOT_USERNAME,
    START_MESSAGE, MOVIE_NOT_FOUND_FOR_USER, MOVIE_NOT_FOUND_INLINE,
    KEYBOARD_TEXTS, ADMIN_COMMANDS, MEMBERSHIP_REQUIRED_MESSAGE
)
from movie_manager import MovieManager
from user_manager import UserManager
from channel_manager import ChannelManager
from payment_manager import PaymentManager
from broadcast_manager import BroadcastManager
from tmdb_handler import TMDBHandler

def validate_config():
    """Konfiguratsiya tekshiruvi"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN mavjud emas!")
        return False
    if not ADMIN_CHAT_ID:
        print("❌ ADMIN_CHAT_ID mavjud emas!")
        return False
    if not BOT_USERNAME:
        print("❌ BOT_USERNAME mavjud emas!")
        return False
    print("✅ Konfiguratsiya tekshiruvi muvaffaqiyatli!")
    return True

# Konfiguratsiya tekshirish
if not validate_config():
    print("Dastur konfiguratsiyadagi xatoliklar tufayli ishga tushmadi!")
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
bot = telebot.TeleBot(BOT_TOKEN)
try:
    # ADMIN_CHAT_ID matnini vergul bo'yicha ajratib, har birini songa o'giramiz
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_CHAT_ID.split(',')]
    print(f"✅ Admin ID lar muvaffaqiyatli yuklandi: {ADMIN_IDS}")
except (ValueError, AttributeError):
    ADMIN_IDS = []
    print("❌ ADMIN_CHAT_ID noto'g'ri formatda yoki mavjud emas!")
    # Agar admin ID umuman bo'lmasa yoki xato bo'lsa, botni to'xtatish muhim
    if not ADMIN_CHAT_ID or ADMIN_CHAT_ID == "0":
         print("Dastur ADMIN_CHAT_ID sozlanmagani uchun to'xtatildi!")
         exit(1)

user_states = {}
temp_movie_data = {}

# Managerlarni ishga tushirish
payment_manager = PaymentManager()
movie_manager = MovieManager()
user_manager = UserManager(payment_manager)
channel_manager = ChannelManager()
broadcast_manager = BroadcastManager()
tmdb_handler = TMDBHandler()
# Standart rasm URL manzili
DEFAULT_POSTER_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTVQlpdEJw8JCwIhv8s33VI2LojHEbbvdOc5w&s"

def is_user_member(user_id):
    """Foydalanuvchi kanalga a'zo ekanligini tekshirish"""
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
                member = bot.get_chat_member(f"@{channel['username']}", user_id)
                if member.status in ['member', 'administrator', 'creator']:
                    continue
                else:
                    return False
            except Exception as e:
                logger.warning(f"Kanal a'zoligini tekshirishda xatolik {channel['username']}: {e}")
                return False
        return True
    except Exception as e:
        logger.error(f"A'zolik tekshirishda xatolik: {e}")
        return True

def get_subscription_keyboard():
    """Obuna klaviaturasi"""
    try:
        keyboard = types.InlineKeyboardMarkup()
        channels = channel_manager.get_channel_list_for_check()
        for channel in channels:
            keyboard.add(types.InlineKeyboardButton(f"📢 {channel['name']}", url=channel['url']))
        keyboard.add(types.InlineKeyboardButton(KEYBOARD_TEXTS['check_subscription'], callback_data='check_subscription'))
        prices = payment_manager.get_prices()
        keyboard.add(types.InlineKeyboardButton(f"💎 Premium ({prices['week']:,} so'm/hafta)", callback_data='show_premium'))
        return keyboard
    except Exception as e:
        logger.error(f"Obuna klaviaturasi yaratishda xatolik: {e}")
        return types.InlineKeyboardMarkup()

def get_main_keyboard(user_id):
    """Asosiy klaviatura"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    # Birinchi qator
    search_btn = types.KeyboardButton(KEYBOARD_TEXTS['search'])
    genres_btn = types.KeyboardButton(KEYBOARD_TEXTS['genres'])
    keyboard.add(search_btn, genres_btn)

    # Ikkinchi qator
    top_movies_btn = types.KeyboardButton(KEYBOARD_TEXTS['top_movies'])
    latest_movies_btn = types.KeyboardButton(KEYBOARD_TEXTS['latest_movies'])
    keyboard.add(top_movies_btn, latest_movies_btn)

    # Uchinchi qator (Premium)
    if payment_manager.is_premium_user(user_id):
        premium_btn = types.KeyboardButton(KEYBOARD_TEXTS['premium'] + " ✅")
    else:
        premium_btn = types.KeyboardButton(KEYBOARD_TEXTS['premium'])
    keyboard.add(premium_btn)

    # To'rtinchi qator (Admin)
    if user_id in ADMIN_IDS:
        admin_btn = types.KeyboardButton(KEYBOARD_TEXTS['admin'])
        keyboard.add(admin_btn)

    return keyboard

def get_admin_keyboard():
    """Admin klaviaturasi"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton(ADMIN_COMMANDS['add_video']),
        types.KeyboardButton(ADMIN_COMMANDS['delete_video'])
    )
    keyboard.add(
        types.KeyboardButton(ADMIN_COMMANDS['stats']),
        types.KeyboardButton(ADMIN_COMMANDS['broadcast'])
    )
    keyboard.add(
        types.KeyboardButton(ADMIN_COMMANDS['manage_channels']),
        types.KeyboardButton(ADMIN_COMMANDS['manage_users'])
    )
    keyboard.add(
        types.KeyboardButton(ADMIN_COMMANDS['premium_settings']),
        types.KeyboardButton(ADMIN_COMMANDS['payment_requests'])
    )
    keyboard.add(types.KeyboardButton(KEYBOARD_TEXTS['back']))
    return keyboard

def safe_send_message(chat_id, text, **kwargs):
    """Xabar yuborishda xatolik handle qilish"""
    for attempt in range(3):
        try:
            return bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik (chat_id: {chat_id}, urinish {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(1)
    return None

def safe_edit_message(chat_id, message_id, text, **kwargs):
    """Xabarni tahrirlashda xatolik handle qilish"""
    for attempt in range(3):
        try:
            return bot.edit_message_text(text, chat_id, message_id, **kwargs)
        except Exception as e:
            logger.error(f"Xabarni tahrirlashda xatolik (urinish {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(1)
    return None

def generate_movie_caption(movie_data, movie_id, views):
    """Film caption yaratish"""
    title = movie_data.get('title', "Noma'lum film")
    original_title = movie_data.get('original_title')
    caption = f"🎬 <b>{title}</b>"
    if original_title and original_title.lower() != title.lower():
        caption += f" ({original_title})"
    caption += f"\n➖➖➖➖➖➖➖➖➖➖\n"
    if movie_data.get('countries'):
        caption += f"🌍 Davlat: {', '.join(movie_data['countries'])}\n"
    if movie_data.get('genres'):
        caption += f"🎭 Janr: {' '.join(['#' + g.replace(' ', '') for g in movie_data['genres']])}\n"
    if movie_data.get('year'):
        caption += f"📆 Yil: {movie_data['year']}\n"
    if movie_data.get('rating') and movie_data['rating'] > 0:
        caption += f"⭐ Reyting: {movie_data['rating']}\n"
    caption += f"\n🔢 Kod: {movie_id}\n👁 Ko'rishlar: {views}\n\n✅ @{BOT_USERNAME.replace('@','')} | Filmlar olami 🍿"
    return caption

def send_movie(chat_id, movie_id):
    """Film yuborish"""
    try:
        user_manager.add_user(chat_id)
        user_manager.update_user_activity(chat_id)
        if not is_user_member(chat_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 @{ch['username']}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            # 2-TUZATISH: parse_mode='HTML' qo'shildi
            safe_send_message(chat_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return
        movie_data = movie_manager.get_movie(movie_id)
        if not movie_data:
            safe_send_message(chat_id, MOVIE_NOT_FOUND_FOR_USER.format(username=BOT_USERNAME.replace('@', '')), parse_mode='HTML')
            return
        views = movie_manager.update_views(movie_id)
        user_manager.increment_movie_watch(chat_id)
        caption = generate_movie_caption(movie_data, movie_id, views)
        keyboard = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("↪️ Ulashish", switch_inline_query=movie_data.get('title', ''))],
            [types.InlineKeyboardButton("🔎 Boshqa kinolarni qidirish", switch_inline_query_current_chat="")]
        ])
        bot.send_video(chat_id, movie_data['file_id'], caption=caption, parse_mode='HTML', reply_markup=keyboard)
        logger.info(f"Film yuborildi: ID {movie_id}, Chat ID {chat_id}")
    except Exception as e:
        logger.error(f"Video yuborishda xatolik: {e}")
        safe_send_message(chat_id, "❌ Video yuborishda xatolik yuz berdi.")

# >>>>>>>>>>>>>>>>>>>> YANGI KOD BLOKI <<<<<<<<<<<<<<<<<<<<<<<

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
    """Ommaviy xabar uchun istalgan turdagi kontentni qabul qilish"""
    admin_id = message.from_user.id
    try:
        user_list = user_manager.get_users_for_broadcast()
        if not user_list:
            safe_send_message(admin_id, "❌ Xabar yuborish uchun (premium bo'lmagan) foydalanuvchilar topilmadi.")
            user_states.pop(admin_id, None)
            return

        sent_count = 0
        failed_count = 0

        confirmation_msg = safe_send_message(admin_id, f"⏳ Ommaviy xabar yuborish boshlandi... Jami: {len(user_list)} ta foydalanuvchi.")

        start_time = time.time()

        for user_id in user_list:
            if send_broadcast_message(user_id, message.chat.id, message.message_id, reply_markup=message.reply_markup):
                sent_count += 1
            else:
                failed_count += 1

            if (sent_count + failed_count) % 25 == 0:
                time.sleep(1)

        end_time = time.time()
        total_time = round(end_time - start_time)

        result_text = f"✅ Ommaviy xabar yuborish yakunlandi!\n\n" \
                      f"👥 Jami foydalanuvchilar: {len(user_list)}\n" \
                      f"👍 Muvaffaqiyatli yuborildi: {sent_count}\n" \
                      f"👎 Xatolik yuz berdi: {failed_count}\n" \
                      f"⏱️ Sarflangan vaqt: {total_time} soniya"

        if confirmation_msg:
            safe_edit_message(admin_id, confirmation_msg.message_id, result_text)
        else:
            safe_send_message(admin_id, result_text)

    except Exception as e:
        logger.error(f"Ommaviy xabar yuborishda umumiy xatolik: {e}")
        safe_send_message(admin_id, "❌ Ommaviy xabar yuborishda kutilmagan xatolik yuz berdi.")
    finally:
        user_states.pop(admin_id, None)

# >>>>>>>>>>>>>>>>>>>> YANGI KOD BLOKI TUGADI <<<<<<<<<<<<<<<<<<<<<<<

@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        user_manager.add_user(user_id, username, first_name, last_name)
        if user_manager.is_banned(user_id):
            safe_send_message(user_id, "❌ Siz botdan foydalanish uchun bloklangansiz.")
            return
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            send_movie(user_id, int(parts[1]))
            return
        safe_send_message(user_id, START_MESSAGE, reply_markup=get_main_keyboard(user_id), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Start komandasi xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['search'])
def search_request(message):
    try:
        user_id = message.from_user.id
        user_manager.update_user_activity(user_id)
        if not is_user_member(user_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 @{ch['username']}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            # 2-TUZATISH: parse_mode='HTML' qo'shildi
            safe_send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return
        text = "Kinoni topish uchun uning nomini yoki kino kodini yozing.\n\nYoki ayrim kinolarni ko'rish uchun quyidagi tugmani bosing:"
        keyboard = types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("🔎 kinolarni ko'rish", switch_inline_query_current_chat="")
        ]])
        safe_send_message(user_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Qidiruv so'rovi xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def check_subscription(call):
    try:
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        if is_user_member(user_id):
            safe_edit_message(call.message.chat.id, call.message.message_id, "✅ Tabriklaymiz! Endi botdan to'liq foydalanishingiz mumkin.", reply_markup=None)
        else:
            bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    except Exception as e:
        logger.error(f"Obuna tekshirishda xatolik: {e}")

@bot.inline_handler(func=lambda query: True)
def inline_search(query):
    try:
        user_id = query.from_user.id
        if not is_user_member(user_id):
            no_access = types.InlineQueryResultArticle(
                id='0',
                title="🔒 Botdan foydalanish uchun kanallarga obuna bo'ling",
                description="Inline qidiruv faqat a'zolar uchun",
                input_message_content=types.InputTextMessageContent("🔒 Botdan foydalanish uchun majburiy kanallarga obuna bo'ling!\n\n/start - Obuna bo'lish")
            )
            bot.answer_inline_query(query.id, [no_access], cache_time=10)
            return
        search_query = query.query.strip().lower()
        movies = movie_manager.search_movies(search_query)
        results = []
        if not movies:
            no_result = types.InlineQueryResultArticle(
                id='0',
                title="❌ Film topilmadi",
                description="🔍 Boshqa kalit so'zlar bilan qidiring yoki film kodini kiriting",
                input_message_content=types.InputTextMessageContent(MOVIE_NOT_FOUND_FOR_USER.format(username=BOT_USERNAME.replace('@', '')), parse_mode='HTML')
            )
            bot.answer_inline_query(query.id, [no_result], cache_time=10)
            return
        for movie_id, data in list(movies.items())[:50]:
            title = data.get('title', 'Noma\'lum film')
            views = data.get('views', 0)
            poster_url = data.get('poster_url')
            rating = data.get('rating', 0.0)
            quality_str = "1080p | BluRay" if rating >= 7.5 else "1080p | WEB-DL"
            first_line = f"{movie_id} | {quality_str} | 👁 {views}"
            languages = "O'zbek, Ingliz, Rus"
            second_line = f"🚩 {languages}"
            description = f"{first_line}\n{second_line}"
            result = types.InlineQueryResultArticle(
                id=str(movie_id),
                title=title,
                description=description,
                thumbnail_url=poster_url if poster_url else None,
                input_message_content=types.InputTextMessageContent(f"/start {movie_id}")
            )
            results.append(result)
        bot.answer_inline_query(query.id, results, cache_time=300)
        logger.info(f"Inline qidiruv: '{search_query}' uchun {len(results)} ta natija yuborildi.")
    except Exception as e:
        logger.error(f"Inline qidiruvda kutilmagan xatolik: {e}", exc_info=True)
        try:
            bot.answer_inline_query(query.id, [])
        except Exception as api_err:
            logger.error(f"Inline xatolik javobini yuborib bo'lmadi: {api_err}")




def generate_movie_list_text(movies, list_title):
    """Kino ro'yxatini matn ko'rinishida formatlash"""
    if not movies:
        return f"Hozircha {list_title.lower()} topilmadi."

    text = f"<b>{list_title}:</b>\n\n"
    for i, (movie_id, data) in enumerate(movies.items(), 1):
        title = data.get('title', 'Noma\'lum')
        year = data.get('year', '')
        rating = data.get('rating', 0.0)
        text += f"<b>{i}. {title}</b> ({year}) - ⭐ {rating}\n"
        text += f"Kinoni ko'rish uchun yuboring: <code>{movie_id}</code>\n\n"
    return text

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['top_movies'])
def handle_top_movies(message):
    """Eng ommabop kinolar ro'yxatini yuborish"""
    try:
        user_id = message.from_user.id
        user_manager.update_user_activity(user_id)

        if not is_user_member(user_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 @{ch['username']}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            safe_send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return

        all_movies = movie_manager.get_all_movies()
        # Kinolarni ko'rishlar soni bo'yicha saralash
        sorted_movies = sorted(all_movies.items(), key=lambda item: item[1].get('views', 0), reverse=True)

        top_10_movies = dict(sorted_movies[:10])

        text = generate_movie_list_text(top_10_movies, "🏆 Eng Ommabop 10 Kino")
        safe_send_message(user_id, text, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Top kinolarni ko'rsatishda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['latest_movies'])
def handle_latest_movies(message):
    """Eng so'nggi qo'shilgan kinolar ro'yxatini yuborish"""
    try:
        user_id = message.from_user.id
        user_manager.update_user_activity(user_id)

        if not is_user_member(user_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 @{ch['username']}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            safe_send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return

        all_movies = movie_manager.get_all_movies() # Bu allaqachon sanasi bo'yicha saralangan

        latest_10_movies = dict(list(all_movies.items())[:10])

        text = generate_movie_list_text(latest_10_movies, "✨ Eng So'nggi Qo'shilgan Kinolar")
        safe_send_message(user_id, text, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Yangi kinolarni ko'rsatishda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text == KEYBOARD_TEXTS['genres'])
def handle_genres(message):
    """Janrlar menyusini ko'rsatish"""
    try:
        user_id = message.from_user.id
        user_manager.update_user_activity(user_id)

        if not is_user_member(user_id):
            prices = payment_manager.get_prices()
            text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                channels="\n".join([f"📢 @{ch['username']}" for ch in channel_manager.get_channel_list_for_check()]),
                week_price=prices['week'],
                month_price=prices['month'],
                year_price=prices['year']
            )
            safe_send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
            return

        all_movies = movie_manager.get_all_movies()
        genres = set()
        for movie_data in all_movies.values():
            for genre in movie_data.get('genres', []):
                genres.add(genre)

        if not genres:
            safe_send_message(user_id, "Hozircha janrlar mavjud emas.")
            return

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(genre, callback_data=f"genre_{genre}") for genre in sorted(list(genres))]
        keyboard.add(*buttons)

        safe_send_message(user_id, "🎭 Kerakli janrni tanlang:", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Janrlarni ko'rsatishda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('genre_'))
def handle_genre_selection(call):
    """Tanlangan janr bo'yicha kinolarni ko'rsatish"""
    try:
        bot.answer_callback_query(call.id)
        selected_genre = call.data.split('_', 1)[1]

        all_movies = movie_manager.get_all_movies()

        genre_movies = {}
        for movie_id, data in all_movies.items():
            if selected_genre in data.get('genres', []):
                genre_movies[movie_id] = data

        # Ko'rishlar soni bo'yicha saralash
        sorted_genre_movies = dict(sorted(genre_movies.items(), key=lambda item: item[1].get('views', 0), reverse=True)[:10])

        text = generate_movie_list_text(sorted_genre_movies, f"🎭 {selected_genre} Janridagi Kinolar (Top 10)")
        # Xabarni tahrirlash o'rniga yangi xabar yuboramiz, chunki ro'yxat uzun bo'lishi mumkin
        safe_send_message(call.message.chat.id, text, parse_mode='HTML')
        # Eski "Janrni tanlang" xabarini o'chirish (ixtiyoriy)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    except Exception as e:
        logger.error(f"Janr bo'yicha kinolarni ko'rsatishda xatolik: {e}")


@bot.message_handler(func=lambda msg: msg.text and (msg.text == KEYBOARD_TEXTS['premium'] or msg.text == KEYBOARD_TEXTS['premium'] + " ✅"))
def handle_premium(message):
    try:
        user_id = message.from_user.id
        user_manager.update_user_activity(user_id)
        if payment_manager.is_premium_user(user_id):
            premium_info = payment_manager.get_premium_info(user_id)
            from datetime import datetime
            expire_date = datetime.fromisoformat(premium_info['expire_date'])
            text = f"""✅ <b>Premium obuna faol!</b>

📅 <b>Boshlangan sana:</b> {premium_info['start_date'][:10]}
⏰ <b>Tugash sanasi:</b> {expire_date.strftime('%d.%m.%Y')}
💎 <b>Reja:</b> {premium_info['plan_type'].title()}

🎯 <b>Sizning imkoniyatlaringiz:</b>
• Kanallarga a'zo bo'lish majburiyati yo'q
• Reklamasiz foydalanish
• Tezkor qidiruv va yuklash"""
            safe_send_message(user_id, text, parse_mode='HTML')
        else:
            prices = payment_manager.get_prices()
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(f"📅 1 hafta - {prices['week']:,} so'm", callback_data='premium_week'))
            keyboard.add(types.InlineKeyboardButton(f"📅 1 oy - {prices['month']:,} so'm", callback_data='premium_month'))
            keyboard.add(types.InlineKeyboardButton(f"📅 1 yil - {prices['year']:,} so'm", callback_data='premium_year'))
            text = f"""💎 <b>Premium Obuna</b>

🎯 <b>Premium imkoniyatlari:</b>
• 🚫 Kanallarga a'zo bo'lish majburiyati yo'q
• 🎯 Reklamasiz foydalanish
• ⚡ Tezkor qidiruv va yuklash
• 🆕 Eng yangi filmlar birinchi bo'lib

💰 <b>Narxlar:</b>"""
            safe_send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Premium handle xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.from_user.id in ADMIN_IDS and msg.text and (msg.text in KEYBOARD_TEXTS.values() or msg.text in ADMIN_COMMANDS.values()))
def handle_admin_keyboard(message):
    """Admin klaviatura handleri"""
    try:
        user_id = message.from_user.id

        if message.text == ADMIN_COMMANDS['broadcast']:
            safe_send_message(user_id, "📢 Ommaviy xabar uchun postni menga yuboring yoki forward qiling.\n\nBu matn, rasm, video yoki boshqa istalgan turdagi xabar bo'lishi mumkin.")
            user_states[user_id] = 'broadcast_message'
        elif message.text == KEYBOARD_TEXTS['admin']:
            safe_send_message(user_id, "⚙️ Admin Panel", reply_markup=get_admin_keyboard())
        elif message.text == KEYBOARD_TEXTS['back']:
            user_states.pop(user_id, None)
            temp_movie_data.clear()
            safe_send_message(user_id, "🏠 Asosiy menyu", reply_markup=get_main_keyboard(user_id))
        elif message.text == ADMIN_COMMANDS['add_video']:
            safe_send_message(user_id, "📹 Qo'shmoqchi bo'lgan video faylni o'zbekcha sarlavha (caption) bilan yuboring.")
            user_states[user_id] = 'adding_video'
        elif message.text == ADMIN_COMMANDS['stats']:
            try:
                movie_stats = movie_manager.get_stats()
                user_stats = user_manager.get_user_stats()
                payment_stats = payment_manager.get_payment_stats()
                text = f"""📊 Bot Statistikasi\n\n🎬 <b>Filmlar:</b>\n• Jami filmlar: {movie_stats['total_movies']}\n• Jami ko'rishlar: {movie_stats['total_views']}\n\n👥 <b>Foydalanuvchilar:</b>\n• Jami foydalanuvchilar: {user_stats['total_users']}\n• Faol foydalanuvchilar: {user_stats['active_users']}\n• Premium foydalanuvchilar: {payment_stats['active_premium_users']}\n\n💰 <b>To'lovlar:</b>\n• Jami to'lovlar: {payment_stats['total_payments']}\n• Kutilayotgan: {payment_stats['pending_payments']}\n• Jami daromad: {payment_stats['total_earned']:,} so'm"""
                safe_send_message(user_id, text, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Statistika olishda xatolik: {e}")
                safe_send_message(user_id, "❌ Statistikani olishda xatolik yuz berdi.")
        elif message.text == ADMIN_COMMANDS['manage_channels']:
            text = generate_channels_list_text()
            keyboard = get_channels_management_keyboard()
            safe_send_message(user_id, text, reply_markup=keyboard, parse_mode='HTML')
        elif message.text == ADMIN_COMMANDS['premium_settings']:
            try:
                prices = payment_manager.get_prices()
                card_info = payment_manager.get_card_info()
                text = f"""💎 <b>Premium sozlamalari</b>\n\n💰 <b>Joriy narxlar:</b>\n• 1 hafta: {prices['week']:,} so'm\n• 1 oy: {prices['month']:,} so'm\n• 1 yil: {prices['year']:,} so'm\n\n💳 <b>To'lov ma'lumotlari:</b>\n• Karta: {card_info['card_number']}\n• Egasi: {card_info['card_holder']}\n• Bank: {card_info['bank_name']}\n\n💡 Sozlamalarni o'zgartirish uchun quyidagi tugmalardan foydalaning:"""
                keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("💰 Narxlarni o'zgartirish", callback_data='change_prices')], [types.InlineKeyboardButton("💳 Karta ma'lumotlarini o'zgartirish", callback_data='change_card')]])
                safe_send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Premium sozlamalarda xatolik: {e}")
                safe_send_message(user_id, "❌ Premium sozlamalarni yuklashda xatolik.")
        elif message.text == ADMIN_COMMANDS['payment_requests']:
            try:
                pending_payments = payment_manager.get_pending_payments()
                if not pending_payments:
                    safe_send_message(user_id, "💳 Kutilayotgan to'lov so'rovlari yo'q.")
                else:
                    text = f"💳 <b>Kutilayotgan to'lovlar ({len(pending_payments)} ta):</b>\n\n"
                    for payment_id, data in list(pending_payments.items())[:10]:
                        username_display = f"@{data['username']}" if data['username'] != 'Noma\'lum' else "Username yo'q"
                        text += f"🆔 {payment_id}\n👤 {username_display}\n💰 {data['amount']:,} so'm ({data['plan_type']})\n📅 {data['created_at'][:10]}\n\n"
                    text += "💡 To'lovni ko'rish uchun ID raqamini yuboring."
                    safe_send_message(user_id, text, parse_mode='HTML')
                    user_states[user_id] = 'view_payments'
            except Exception as e:
                logger.error(f"To'lov so'rovlari yuklanmadi: {e}")
                safe_send_message(user_id, "❌ To'lov so'rovlarini yuklashda xatolik.")
        elif message.text == ADMIN_COMMANDS['delete_video']:
            safe_send_message(user_id, "🗑 O'chirmoqchi bo'lgan kinoning ID raqamini yuboring:")
            user_states[user_id] = 'delete_video'
        elif message.text == ADMIN_COMMANDS['manage_users']:
            safe_send_message(user_id, "👥 Topmoqchi bo'lgan foydalanuvchining ID raqamini yoki @username'ini yuboring:")
            user_states[user_id] = 'find_user'
    except Exception as e:
        logger.error(f"Admin keyboard handle xatolik: {e}")
@bot.message_handler(content_types=['video'], func=lambda msg: user_states.get(msg.from_user.id) == 'adding_video')
def handle_video_upload(message):
    admin_id = message.from_user.id
    msg_to_edit = None
    try:
        uzbek_title, _, _ = tmdb_handler.parse_caption(message.caption or '')
        if not uzbek_title:
            safe_send_message(admin_id, "❌ Video sarlavhasi (caption) bo'sh. Iltimos, film nomini kiriting.")
            return
        logger.info(f"Video yuklash boshlandi: {uzbek_title}")
        msg_to_edit = safe_send_message(admin_id, f"⏳ '{uzbek_title}' uchun ma'lumotlar qidirilmoqda...")
        if not msg_to_edit:
            safe_send_message(admin_id, "❌ Xabar yuborishda xatolik.")
            return
        logger.info(f"TMDB'dan qidirilmoqda: {uzbek_title}")
        tmdb_results = tmdb_handler.search_movie(uzbek_title)
        if not tmdb_results:
            logger.warning(f"'{uzbek_title}' uchun TMDB'dan natija topilmadi. Standart rasm bilan qo'shilmoqda.")
            fallback_movie_data = {'file_id': message.video.file_id, 'title': uzbek_title, 'poster_url': DEFAULT_POSTER_URL, 'original_title': '', 'overview': '', 'year': '', 'rating': 0.0, 'genres': [], 'countries': [], 'tmdb_id': None}
            new_id = movie_manager.get_next_id()
            save_result = movie_manager.add_movie(new_id, fallback_movie_data)
            if save_result:
                success_text = f"✅ Film TMDB ma'lumotlarisiz qo'shildi!\n\n🆔 Kino kodi: {new_id}\n🎬 Nomi: {uzbek_title}"
                safe_edit_message(admin_id, msg_to_edit.message_id, success_text)
            else:
                error_text = "❌ Filmni ma'lumotlar bazasiga saqlashda xatolik yuz berdi."
                safe_edit_message(admin_id, msg_to_edit.message_id, error_text)
            user_states.pop(admin_id, None)
            return
        logger.info(f"TMDB natijasi: {len(tmdb_results)} film topildi")
        temp_key = f"{admin_id}_{message.message_id}"
        temp_movie_data[temp_key] = {'file_id': message.video.file_id, 'title': uzbek_title, 'admin_id': admin_id, 'msg_id': msg_to_edit.message_id}
        logger.info(f"Temp ma'lumot saqlandi: {temp_key}")
        keyboard = types.InlineKeyboardMarkup()
        for i, movie in enumerate(tmdb_results[:5]):
            year = movie.get('release_date', 'N/A')[:4] if movie.get('release_date') else 'N/A'
            btn_text = f"{movie['title']} ({year})"
            callback_data = f"confirm_{movie['id']}_{temp_key}"
            keyboard.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
        keyboard.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{temp_key}"))
        safe_edit_message(admin_id, msg_to_edit.message_id, f"👇 '{uzbek_title}' uchun topilgan natijalardan birini tanlang:", reply_markup=keyboard)
        logger.info(f"Tanlash tugmalari ko'rsatildi: {temp_key}")
    except Exception as e:
        logger.error(f"Video yuklashda kutilmagan xatolik: {e}", exc_info=True)
        if msg_to_edit:
            safe_edit_message(admin_id, msg_to_edit.message_id, "❌ Video qo'shishda kutilmagan xatolik yuz berdi.")
        else:
            safe_send_message(admin_id, "❌ Video qo'shishda kutilmagan xatolik yuz berdi.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_', 'cancel_')))
def handle_tmdb_confirmation(call):
    temp_key = None
    try:
        logger.info(f"Callback qabul qilindi: {call.data}")
        try:
            bot.answer_callback_query(call.id)
            logger.debug("Callback javob berildi")
        except Exception as e:
            logger.warning(f"Callback javob berishda xatolik: {e}")
        if call.data.startswith('cancel_'):
            temp_key = call.data.replace('cancel_', '')
            logger.info(f"Bekor qilish so'rovi: {temp_key}")
            if temp_key in temp_movie_data:
                temp_movie_data.pop(temp_key)
            safe_edit_message(call.message.chat.id, call.message.message_id, "❌ Video qo'shish bekor qilindi.")
            user_states.pop(call.from_user.id, None)
            return
        parts = call.data.split('_', 2)
        if len(parts) != 3:
            raise ValueError(f"Noto'g'ri callback format: {call.data}")
        _, tmdb_id_str, temp_key = parts
        logger.info(f"TMDB tasdiqlash: tmdb_id={tmdb_id_str}, temp_key={temp_key}")
        movie_data = temp_movie_data.get(temp_key)
        if not movie_data:
            logger.warning(f"Temp ma'lumot topilmadi: {temp_key}")
            safe_edit_message(call.message.chat.id, call.message.message_id, "❌ Xatolik: Vaqt o'tib ketdi yoki ma'lumot topilmadi.\n\n💡 Qaytadan video yuklang.")
            return
        edit_result = safe_edit_message(call.message.chat.id, call.message.message_id, "⏳ Ma'lumotlar birlashtirilmoqda, iltimos kuting...")
        logger.info(f"Birlashtirish xabari yuborildi: {edit_result is not None}")
        details = tmdb_handler.get_movie_details(int(tmdb_id_str))
        if not details:
            logger.error(f"TMDB'dan ma'lumot olinmadi: ID {tmdb_id_str}")
            safe_edit_message(call.message.chat.id, call.message.message_id, f"❌ TMDB'dan ID {tmdb_id_str} uchun ma'lumot olib bo'lmadi.")
            return
        movie_data.update(details)
        new_id = movie_manager.get_next_id()
        save_result = movie_manager.add_movie(new_id, movie_data)
        if save_result:
            success_text = f"✅ Film muvaffaqiyatli qo'shildi!\n\n🆔 Kino kodi: {new_id}\n🎬 Nomi: {movie_data['title']}\n🎭 Janr: {', '.join(movie_data.get('genres', []))}\n📆 Yil: {movie_data.get('year', 'N/A')}\n⭐ Reyting: {movie_data.get('rating', 'N/A')}"
            safe_edit_message(call.message.chat.id, call.message.message_id, success_text)
            try:
                if PRIVATE_CHANNEL_ID and PRIVATE_CHANNEL_ID != 0:
                    views = movie_manager.update_views(new_id)
                    caption = generate_movie_caption(movie_data, new_id, views)
                    bot.send_video(PRIVATE_CHANNEL_ID, movie_data['file_id'], caption=caption, parse_mode='HTML')
                    logger.info(f"Film maxfiy kanalga yuborildi (ID: {new_id})")
            except Exception as e:
                logger.warning(f"Maxfiy kanalga yuborishda xatolik (ID: {new_id}): {e}")
            logger.info(f"Film to'liq qo'shildi: ID {new_id}, Nomi: {movie_data['title']}")
        else:
            logger.error("Ma'lumotlar bazasiga saqlashda xatolik")
            safe_edit_message(call.message.chat.id, call.message.message_id, "❌ Filmni ma'lumotlar bazasiga saqlashda xatolik yuz berdi.")
    except Exception as e:
        logger.error(f"TMDB tasdiqlashda KRITIK xatolik: {e}", exc_info=True)
        safe_edit_message(call.message.chat.id, call.message.message_id, "❌ Kutilmagan jiddiy xatolik yuz berdi.")
    finally:
        if temp_key and temp_key in temp_movie_data:
            logger.info(f"Temp ma'lumot tozalanmoqda: {temp_key}")
            temp_movie_data.pop(temp_key)
        user_states.pop(call.from_user.id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_'))
def handle_premium_purchase(call):
    try:
        bot.answer_callback_query(call.id)
        plan_type = call.data.replace('premium_', '')
        prices = payment_manager.get_prices()
        card_info = payment_manager.get_card_info()
        amount = prices.get(plan_type, 0)
        if amount == 0:
            bot.answer_callback_query(call.id, "❌ Noto'g'ri reja turi!", show_alert=True)
            return
        plan_names = {'week': '1 hafta', 'month': '1 oy', 'year': '1 yil'}
        from config import PAYMENT_INSTRUCTION_MESSAGE
        text = PAYMENT_INSTRUCTION_MESSAGE.format(amount=amount, duration=plan_names[plan_type], card_number=card_info['card_number'], card_holder=card_info['card_holder'], bank_name=card_info['bank_name'])
        keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("✅ To'lov qildim", callback_data=f"paid_{plan_type}_{amount}")]])
        safe_edit_message(call.message.chat.id, call.message.message_id, text, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Premium sotib olishda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def handle_payment_confirmation(call):
    try:
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        parts = call.data.split('_')
        plan_type = parts[1]
        amount = int(parts[2])
        text = "📸 To'lov chekini rasm (screenshot) yoki PDF formatda yuboring.\n\n⚠️ Faqat yuqorida ko'rsatilgan karta raqamiga to'lov qiling!"
        safe_edit_message(call.message.chat.id, call.message.message_id, text)
        user_states[user_id] = f'payment_screenshot_{plan_type}_{amount}'
    except Exception as e:
        logger.error(f"To'lov tasdiqlashda xatolik: {e}")

@bot.message_handler(content_types=['photo', 'document'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].startswith('payment_screenshot_'))
def handle_payment_proof(message):
    """To'lov isbotini (rasm yoki hujjat) qabul qilish"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        state = user_states[user_id]
        parts = state.split('_')
        plan_type = parts[2]
        amount = int(parts[3])
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        if not file_id:
             safe_send_message(user_id, "❌ Fayl qabul qilinmadi. Iltimos, rasm yoki PDF yuboring.")
             return
        payment_id = payment_manager.create_payment_request(user_id, username, plan_type, amount, file_id)
        if payment_id:
            first_name = message.from_user.first_name or "Noma'lum"
            username_text = f"@{username}" if username else "mavjud_emas"
            admin_text = f"""💳 <b>Yangi to'lov so'rovi!</b>

👤 <b>Foydalanuvchi:</b> {first_name}
🆔 <b>User ID:</b> {user_id}
📝 <b>Username:</b> {username_text}
💰 <b>Summa:</b> {amount:,} so'm
📅 <b>Reja:</b> {plan_type}
🆔 <b>Payment ID:</b> {payment_id}"""
            keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_payment_{payment_id}"), types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment_id}")]])
            for admin_id in ADMIN_IDS:
                try:
                    if message.photo:
                        bot.send_photo(admin_id, file_id, caption=admin_text, parse_mode='HTML', reply_markup=keyboard)
                    elif message.document:
                        bot.send_document(admin_id, file_id, caption=admin_text, parse_mode='HTML', reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Adminга to'lov xabari yuborishda xatolik: {e}")
            safe_send_message(user_id, "✅ To'lov cheki qabul qilindi!\n\n⏳ Admin tomonidan ko'rib chiqilgach sizga xabar beriladi.")
        else:
            safe_send_message(user_id, "❌ To'lov so'rovini yaratishda xatolik yuz berdi.")
        user_states.pop(user_id, None)
    except Exception as e:
        logger.error(f"To'lov isbotini qabul qilishda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ['toggle_membership', 'change_prices', 'change_card'])
def handle_admin_callbacks(call):
    try:
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Sizda ruxsat yo'q!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        if call.data == 'toggle_membership':
            success, message = channel_manager.toggle_membership_check()
            if success:
                safe_edit_message(call.message.chat.id, call.message.message_id, f"✅ {message}")
            else:
                bot.answer_callback_query(call.id, f"❌ {message}", show_alert=True)
        elif call.data == 'change_prices':
            safe_edit_message(call.message.chat.id, call.message.message_id, "💰 Yangi narxlarni quyidagi formatda yuboring:\n\nhafta,oy,yil\n\nMasalan: 15000,40000,350000")
            user_states[user_id] = 'change_prices'
        elif call.data == 'change_card':
            safe_edit_message(call.message.chat.id, call.message.message_id, "💳 Yangi karta ma'lumotlarini quyidagi formatda yuboring:\n\nKARTA_RAQAMI,KARTA_EGASI,BANK_NOMI\n\nMasalan: 8600 0000 0000 0000,ADMIN NOMI,Uzcard")
            user_states[user_id] = 'change_card'
    except Exception as e:
        logger.error(f"Admin callback da xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_payment_', 'reject_payment_')))
def handle_admin_payment_decision(call):
    """Admin to'lov qarori handleri"""
    try:
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Sizda ruxsat yo'q!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        payment_id = int(call.data.split('_')[-1])
        action = 'approve' if call.data.startswith('approve_') else 'reject'
        admin_user = call.from_user
        if action == 'approve':
            success, message = payment_manager.approve_payment(payment_id, admin_user.id)
            if success:
                payment_data = payment_manager._load_data()['payments'][str(payment_id)]
                user_id = payment_data['user_id']
                from datetime import datetime, timedelta
                if payment_data['plan_type'] == 'week':
                    expire_date = datetime.now() + timedelta(days=7)
                elif payment_data['plan_type'] == 'month':
                    expire_date = datetime.now() + timedelta(days=30)
                else:
                    expire_date = datetime.now() + timedelta(days=365)
                from config import PREMIUM_SUCCESS_MESSAGE
                user_text = PREMIUM_SUCCESS_MESSAGE.format(expire_date=expire_date.strftime('%d.%m.%Y'))
                safe_send_message(user_id, user_text, parse_mode='HTML')
                new_caption = call.message.caption + f"\n\n✅ <b>TASDIQLANDI</b>\n" f"👤 Admin: @{admin_user.username or admin_user.first_name}"
                bot.edit_message_caption(caption=new_caption, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=None)
            else:
                bot.answer_callback_query(call.id, f"❌ Xatolik: {message}", show_alert=True)
        else:  # reject
            success, message = payment_manager.reject_payment(payment_id, admin_user.id)
            if success:
                payment_data = payment_manager._load_data()['payments'][str(payment_id)]
                user_id = payment_data['user_id']
                safe_send_message(user_id, "❌ Sizning to'lov so'rovingiz rad etildi.\n\n💡 Agar savollaringiz bo'lsa, admin bilan bog'laning.")
                new_caption = call.message.caption + f"\n\n❌ <b>RAD ETILDI</b>\n" f"👤 Admin: @{admin_user.username or admin_user.first_name}"
                bot.edit_message_caption(caption=new_caption, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=None)
            else:
                bot.answer_callback_query(call.id, f"❌ Xatolik: {message}", show_alert=True)
    except Exception as e:
        logger.error(f"Admin to'lov qarorida xatolik: {e}")


# >>>>>>>>>>>>>>>>>>>> KANAL BOSHQARUVI UCHUN YANGI FUNKSIYALAR <<<<<<<<<<<<<<<<<<<<<<<

def get_channels_management_keyboard():
    """Kanallarni boshqarish uchun inline klaviatura yaratish"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    add_btn = types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")
    remove_btn = types.InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="remove_channel_select")
    toggle_btn = types.InlineKeyboardButton("✏️ Holatini o'zgartirish", callback_data="toggle_channel_select")

    keyboard.add(add_btn)
    keyboard.add(remove_btn, toggle_btn)

    membership_status = channel_manager.is_membership_required()
    toggle_membership_text = "❌ Majburiy a'zolikni o'chirish" if membership_status else "✅ Majburiy a'zolikni yoqish"
    toggle_membership_btn = types.InlineKeyboardButton(toggle_membership_text, callback_data="toggle_membership")
    keyboard.add(toggle_membership_btn)

    return keyboard

def generate_channels_list_text():
    """Kanallar ro'yxatini matn ko'rinishida formatlash"""
    channels = channel_manager.get_all_channels()
    if not channels:
        return "Hozircha majburiy kanallar yo'q."

    text = "📢 <b>Kanallar ro'yxati:</b>\n\n"
    for i, (username, data) in enumerate(channels.items(), 1):
        status = "✅ Faol" if data.get('is_active', True) else "❌ Nofaol"
        name = data.get('name', f'@{username}')
        text += f"{i}. {name} - (<code>@{username}</code>) - {status}\n"
    return text

@bot.callback_query_handler(func=lambda call: call.data.startswith('ch_manage_'))
def handle_channel_management_callbacks(call):
    """Kanallarni boshqarishdagi callback'larni qayta ishlash"""
    try:
        admin_id = call.from_user.id
        parts = call.data.split('_', 3) # 3 ga o'zgartirildi

        # Orqaga qaytishni tekshirish
        if len(parts) >= 3 and parts[2] == 'back':
             bot.answer_callback_query(call.id)
             text = generate_channels_list_text()
             keyboard = get_channels_management_keyboard()
             bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
             return

        action = parts[2]
        username = parts[3]

        msg = ""
        if action == 'delete':
            success, msg = channel_manager.remove_channel(username)
        elif action == 'toggle':
            success, msg = channel_manager.toggle_channel_status(username)

        bot.answer_callback_query(call.id, text=msg, show_alert=True)

        # Har qanday holatda menyuni yangilash
        text = generate_channels_list_text()
        keyboard = get_channels_management_keyboard()
        bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Kanalni boshqarish callback xatoligi: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")

@bot.callback_query_handler(func=lambda call: call.data in ['add_channel', 'remove_channel_select', 'toggle_channel_select', 'toggle_membership'])
def handle_channel_menu_selection(call):
    """Kanallarni boshqarish menyusidagi tugmalarni bosish"""
    try:
        admin_id = call.from_user.id
        channels = channel_manager.get_all_channels()

        if call.data == 'add_channel':
            bot.answer_callback_query(call.id)
            user_states[admin_id] = 'add_channel'
            bot.edit_message_text("➕  kanalingizning linkini (https://t.me/...) yoki @username'ini yuboring.", admin_id, call.message.message_id)
            return

        if call.data == 'toggle_membership':
            success, msg = channel_manager.toggle_membership_check()
            bot.answer_callback_query(call.id, msg)
            # Menyuni yangilash
            text = generate_channels_list_text()
            keyboard = get_channels_management_keyboard()
            bot.edit_message_text(text, admin_id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML')
            return

        if not channels:
            bot.answer_callback_query(call.id, "Hozircha kanallar yo'q!", show_alert=True)
            return

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        action_word = ""

        if call.data == 'remove_channel_select':
            action_word = "O'chirish uchun"
            callback_prefix = "ch_manage_delete_"
        elif call.data == 'toggle_channel_select':
            action_word = "Holatini o'zgartirish uchun"
            callback_prefix = "ch_manage_toggle_"

        for username, data in channels.items():
            name = data.get('name', f'@{username}')
            keyboard.add(types.InlineKeyboardButton(name, callback_data=f"{callback_prefix}{username}"))

        keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="ch_manage_back_"))
        bot.edit_message_text(f"👇 {action_word} kanalni tanlang:", admin_id, call.message.message_id, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Kanal menyusini tanlashda xatolik: {e}")


@bot.message_handler(func=lambda msg: msg.from_user.id in ADMIN_IDS and msg.from_user.id in user_states)
def handle_admin_states(message):
    """Admin holatlarini boshqarish (faqat matnli holatlar uchun)"""
    try:
        user_id = message.from_user.id
        state = user_states.get(user_id)

        if state == 'add_channel':
            success, msg = channel_manager.add_channel(message.text)
            safe_send_message(user_id, msg)
            user_states.pop(user_id, None)
            text = generate_channels_list_text()
            keyboard = get_channels_management_keyboard()
            safe_send_message(user_id, text, reply_markup=keyboard, parse_mode='HTML')
        elif state == 'delete_video':
            try:
                movie_id = int(message.text)
                success, msg = movie_manager.delete_movie(movie_id)
                safe_send_message(user_id, msg)
            except ValueError:
                safe_send_message(user_id, "❌ Noto'g'ri format. Iltimos, faqat kino ID raqamini yuboring.")
            finally:
                user_states.pop(user_id, None)
        elif state == 'find_user':
            try:
                query = message.text
                user_data = user_manager.find_user(query)
                if user_data:
                    user_id_found = user_data.get('user_id')
                    username = user_data.get('username', 'N/A')
                    first_name = user_data.get('first_name', 'N/A')
                    joined_date = user_data.get('joined_date', 'N/A')
                    movies_watched = user_data.get('movies_watched', 0)
                    is_premium = payment_manager.is_premium_user(user_id_found)
                    premium_text = "✅ Ha"
                    if is_premium:
                        premium_info = payment_manager.get_premium_info(user_id_found)
                        if premium_info and premium_info.get('expire_date'):
                            from datetime import datetime
                            expire_date = datetime.fromisoformat(premium_info['expire_date']).strftime('%d.%m.%Y')
                            premium_text += f" (Tugash sanasi: {expire_date})"
                    else:
                        premium_text = "❌ Yo'q"
                    text = f"<b>Foydalanuvchi ma'lumotlari:</b>\n\n👤 <b>Ism:</b> {first_name}\n🆔 <b>User ID:</b> <code>{user_id_found}</code>\n✍️ <b>Username:</b> @{username}\n📅 <b>Qo'shilgan sana:</b> {joined_date[:10]}\n🎬 <b>Ko'rilgan kinolar:</b> {movies_watched} ta\n💎 <b>Premium statusi:</b> {premium_text}"
                    safe_send_message(user_id, text, parse_mode='HTML')
                else:
                    safe_send_message(user_id, f"❌ '{query}' bo'yicha foydalanuvchi topilmadi.")
            finally:
                user_states.pop(user_id, None)
        elif state == 'change_prices':
            try:
                if ',' in message.text:
                    parts = message.text.split(',')
                    if len(parts) == 3:
                        new_prices = {'week': int(parts[0].strip()), 'month': int(parts[1].strip()), 'year': int(parts[2].strip())}
                        if payment_manager.update_prices(new_prices):
                            safe_send_message(user_id, f"✅ Narxlar yangilandi:\n• 1 hafta: {new_prices['week']:,} so'm\n• 1 oy: {new_prices['month']:,} so'm\n• 1 yil: {new_prices['year']:,} so'm")
                        else:
                            safe_send_message(user_id, "❌ Narxlarni saqlashda xatolik.")
                    else:
                        safe_send_message(user_id, "❌ Noto'g'ri format! 3 ta narx kiritish kerak.\nMasalan: 15000,40000,350000")
                        return
                else:
                    safe_send_message(user_id, "❌ Vergul (,) bilan ajrating!\nMasalan: 15000,40000,350000")
                    return
            except ValueError:
                safe_send_message(user_id, "❌ Faqat raqamlar kiriting!")
                return
            finally:
                user_states.pop(user_id, None)
        elif state == 'change_card':
            try:
                if ',' in message.text:
                    parts = message.text.split(',')
                    if len(parts) == 3:
                        new_card = {'card_number': parts[0].strip(), 'card_holder': parts[1].strip(), 'bank_name': parts[2].strip()}
                        if payment_manager.update_card_info(new_card):
                            safe_send_message(user_id, f"✅ Karta ma'lumotlari yangilandi:\n• Karta: {new_card['card_number']}\n• Egasi: {new_card['card_holder']}\n• Bank: {new_card['bank_name']}")
                        else:
                            safe_send_message(user_id, "❌ Karta ma'lumotlarini saqlashda xatolik.")
                    else:
                        safe_send_message(user_id, "❌ Noto'g'ri format! 3 ta ma'lumot kiritish kerak.\nMasalan: 8600 0000 0000 0000,ADMIN,Uzcard")
                        return
                else:
                    safe_send_message(user_id, "❌ Vergul (,) bilan ajrating!\nMasalan: 8600 0000 0000 0000,ADMIN NOMI,Uzcard")
                    return
            finally:
                user_states.pop(user_id, None)
        elif state == 'view_payments':
            try:
                payment_id = int(message.text)
                pending_payments = payment_manager.get_pending_payments()
                if str(payment_id) in pending_payments:
                    data = pending_payments[str(payment_id)]
                    username_display = f"@{data['username']}" if data['username'] != 'Noma\'lum' else "Username yo'q"
                    text = f"""💳 <b>To'lov so'rovi #{payment_id}</b>\n\n👤 <b>Foydalanuvchi:</b> {username_display}\n🆔 <b>User ID:</b> {data['user_id']}\n💰 <b>Summa:</b> {data['amount']:,} so'm\n📅 <b>Reja:</b> {data['plan_type']}\n🕐 <b>Sana:</b> {data['created_at'][:16]}"""
                    keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_payment_{payment_id}"), types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_payment_{payment_id}")]])
                    if data.get('file_id'):
                        try:
                            bot.send_photo(user_id, data['file_id'], caption=text, parse_mode='HTML', reply_markup=keyboard)
                        except:
                            bot.send_document(user_id, data['file_id'], caption=text, parse_mode='HTML', reply_markup=keyboard)
                    else:
                        safe_send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
                else:
                    safe_send_message(user_id, f"❌ To'lov so'rovi #{payment_id} topilmadi yoki allaqachon ko'rib chiqilgan.")
            except Exception as e:
                logger.error(f"To'lov ko'rishda xatolik: {e}")
                safe_send_message(user_id, "❌ To'lovni yuklashda xatolik.")
    except Exception as e:
        logger.error(f"Admin matnli holatlarini boshqarishda xatolik: {e}")

@bot.message_handler(func=lambda msg: msg.text and msg.text.isdigit())
def handle_id_message(message):
    """ID bo'yicha film topish"""
    try:
        if message.from_user.id in ADMIN_IDS and user_states.get(message.from_user.id) == 'view_payments':
            return
        user_manager.update_user_activity(message.from_user.id)
        send_movie(message.chat.id, int(message.text))
    except Exception as e:
        logger.error(f"ID message handle xatolik: {e}")

@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    """Barcha boshqa text xabarlar"""
    try:
        user_id = message.from_user.id
        user_manager.update_user_activity(user_id)
        if user_manager.is_banned(user_id):
            return
        if message.text:
            if not is_user_member(user_id):
                prices = payment_manager.get_prices()
                text = MEMBERSHIP_REQUIRED_MESSAGE.format(
                    channels="\n".join([f"📢 @{ch['username']}" for ch in channel_manager.get_channel_list_for_check()]),
                    week_price=prices['week'],
                    month_price=prices['month'],
                    year_price=prices['year']
                )
                # 2-TUZATISH: parse_mode='HTML' qo'shildi
                safe_send_message(user_id, text, reply_markup=get_subscription_keyboard(), parse_mode='HTML')
                return
            keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton(f"🔎 '{message.text}' bo'yicha qidirish", switch_inline_query_current_chat=message.text)]])
            safe_send_message(user_id, f"'{message.text}' nomli kinoni topish uchun tugmani bosing:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Text message handle xatolik: {e}")

def main():
    try:
        if ADMIN_CHAT_ID:
            safe_send_message(ADMIN_CHAT_ID, "🤖 Bot muvaffaqiyatli ishga tushirildi!")
        logger.info("Bot ishlayapti...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.critical(f"Botning ishlashida jiddiy xatolik: {e}", exc_info=True)
        time.sleep(15)
        main()

if __name__ == '__main__':
    main()
