# migrate.py (YAKUNIY VERSIYA - Xatoliklarni cheklab o'tadi)
import os
import time
import logging
import re

# Loyihaning boshqa qismlarini import qilish
from config import BOT_TOKEN, PRIVATE_CHANNEL_ID, ADMIN_CHAT_ID
from database import init_db
from movie_manager import MovieManager
from tmdb_handler import TMDBHandler
import telebot
from telebot.apihelper import ApiTelegramException

# --- SOZLAMALAR ---
PROCESSED_FILE = "processed_messages.txt"
SLEEP_TIMER = 2 # soniya

# --- Logging sozlamalari ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("migrator")

# --- ASOSIY OBYEKTLAR ---
if not all([BOT_TOKEN, PRIVATE_CHANNEL_ID, ADMIN_CHAT_ID]):
    logger.critical("BOT_TOKEN, PRIVATE_CHANNEL_ID yoki ADMIN_CHAT_ID .env faylda topilmadi!")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)
movie_manager = MovieManager()
tmdb_handler = TMDBHandler()

def load_processed_messages():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    try:
        with open(PROCESSED_FILE, 'r') as f:
            return set(int(line.strip()) for line in f if line.strip().isdigit())
    except IOError as e:
        logger.error(f"Faylni o'qishda xatolik {PROCESSED_FILE}: {e}")
        return set()

def save_processed_message(message_id):
    try:
        with open(PROCESSED_FILE, 'a') as f:
            f.write(f"{message_id}\n")
    except IOError as e:
        logger.error(f"Faylga yozishda xatolik {PROCESSED_FILE}: {e}")

def get_movie_title_from_caption(caption: str) -> str:
    if not caption: return ""
    first_line = caption.split('\n')[0]
    title = re.sub(r'^[🎬 kino]+', '', first_line, flags=re.IGNORECASE).strip()
    return title or first_line

def generate_new_caption(movie_data, new_id):
    title = movie_data.get('title', "Noma'lum film")
    original_title = movie_data.get('original_title')
    caption = f"🎬 {title}"
    if original_title and original_title.lower() != title.lower():
        caption += f" ({original_title})"
    caption += "\n➖➖➖➖➖➖➖➖➖➖\n"
    if movie_data.get('countries'): caption += f"🌍 Davlat: {movie_data['countries']}\n"
    if movie_data.get('genres'):
        genres = movie_data['genres'].split(',')
        caption += f"🎭 Janr: {' '.join(['#' + g.strip().replace(' ', '') for g in genres if g.strip()])}\n"
    if movie_data.get('year'): caption += f"📆 Yil: {movie_data['year']}\n"
    if movie_data.get('rating') and float(movie_data['rating']) > 0:
        caption += f"⭐ Reyting: {movie_data['rating']}\n"
    caption += f"\n🔢 Kod: {new_id}\n👁 Ko'rishlar: 0\n\n✅ @{bot.get_me().username} | Filmlar olami 🍿"
    return caption

def delete_old_message(channel_id, message_id):
    """Xabarni xavfsiz o'chirishga harakat qiladi"""
    try:
        bot.delete_message(channel_id, message_id)
        logger.info(f"Eski xabar #{message_id} o'chirildi.")
    except ApiTelegramException as e:
        if "message can't be deleted" in str(e):
            logger.warning(f"Eski xabarni (#{message_id}) o'chirib bo'lmadi (48 soatdan o'tgan).")
        else:
            logger.error(f"Eski xabarni (#{message_id}) o'chirishda kutilmagan Telegram xatoligi: {e}")

def start_migration():
    logger.info(">>> KANALNI QAYTA ISHLASH SKRIPTI ISHGA TUSHDI <<<")
    processed_ids = load_processed_messages()
    logger.info(f"{len(processed_ids)} ta eski xabar allaqachon qayta ishlangan.")

    try:
        test_msg = bot.send_message(PRIVATE_CHANNEL_ID, "Migratsiya boshlanmoqda...")
        last_message_id = test_msg.message_id
        bot.delete_message(PRIVATE_CHANNEL_ID, last_message_id)
        logger.info(f"Kanaldagi oxirgi xabar ID si: {last_message_id}. Skanerlash boshlandi.")
    except Exception as e:
        logger.critical(f"Kanalga ulanib bo'lmadi! Xatolik: {e}")
        return

    for msg_id in range(last_message_id, 0, -1):
        if msg_id in processed_ids:
            continue

        try:
            logger.info(f"--- Eski xabar #{msg_id} tekshirilmoqda ---")

            message = None
            try:
                temp_chat_id = ADMIN_CHAT_ID.split(',')[0].strip()
                message = bot.forward_message(temp_chat_id, PRIVATE_CHANNEL_ID, msg_id)
                bot.delete_message(temp_chat_id, message.message_id)
            except ApiTelegramException as e:
                if "message to forward not found" in str(e):
                    logger.warning(f"Xabar #{msg_id} topilmadi. O'tkazib yuborildi.")
                    save_processed_message(msg_id)
                    continue
                else:
                    logger.error(f"Xabarni (#_id) olishda xatolik: {e}. 5 soniya kutilmoqda.")
                    time.sleep(5)
                    continue

            if not message or not message.video:
                logger.info(f"Xabar #{msg_id} video emas. O'tkazib yuborildi.")
                save_processed_message(msg_id)
                continue

            video_file_id = message.video.file_id

            existing_movie = movie_manager.get_movie_by_file_id(video_file_id)
            if existing_movie:
                logger.warning(f"Bu file_id ({video_file_id}) bazada allaqachon mavjud (Yangi ID: {existing_movie.id}). Faqat eski xabar o'chiriladi.")
                delete_old_message(PRIVATE_CHANNEL_ID, msg_id) # XAVFSIZ O'CHIRISH
                save_processed_message(msg_id)
                time.sleep(SLEEP_TIMER)
                continue

            movie_title = get_movie_title_from_caption(message.caption)
            if not movie_title:
                movie_title = f"Noma'lum Kino (Eski ID: {msg_id})"

            logger.info(f"Kino nomi topildi: '{movie_title}'")

            details = {}
            tmdb_results = tmdb_handler.search_movie(movie_title)
            if tmdb_results:
                details = tmdb_handler.get_movie_details(tmdb_results[0]['id'])

            movie_data = {'file_id': video_file_id, 'title': movie_title, **(details or {})}
            new_movie_id = movie_manager.add_movie(movie_data)

            if not new_movie_id:
                logger.error(f"Xabar #{msg_id} ni bazaga saqlashda xatolik! O'tkazib yuborildi.")
                continue

            logger.info(f"Film bazaga saqlandi. Yangi ID: {new_movie_id}")

            new_caption = generate_new_caption(movie_data, new_movie_id)
            bot.send_video(PRIVATE_CHANNEL_ID, video_file_id, caption=new_caption, parse_mode='HTML')
            logger.info("Yangi xabar kanalga yuborildi.")

            delete_old_message(PRIVATE_CHANNEL_ID, msg_id) # XAVFSIZ O'CHIRISH

            save_processed_message(msg_id)
            logger.info(f"--- Eski xabar #{msg_id} muvaffaqiyatli qayta ishlandi ---\n")

            time.sleep(SLEEP_TIMER)

        except Exception as e:
            logger.error(f"Xabar #{msg_id} ni qayta ishlashda kutilmagan umumiy xatolik: {e}", exc_info=True)
            logger.info("Jiddiy xatolik tufayli 15 soniya kutilmoqda...")
            time.sleep(15)

    logger.info(">>> MIGTRATSIYA JARAYONI YAKUNLANDI <<<")

if __name__ == "__main__":
    init_db()
    start_migration()
