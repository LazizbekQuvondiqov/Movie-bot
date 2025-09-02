import os
from dotenv import load_dotenv

load_dotenv()

# Asosiy sozlamalar
BOT_TOKEN = os.getenv("BOT_TOKEN")
# >>>>>>>>>>>>>>>>>>>> TUZATISH: Endi bu matn sifatida olinadi <<<<<<<<<<<<<<<<<<<<<<<
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "0")
BOT_USERNAME = os.getenv("BOT_USERNAME", "KinoBot")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "0"))

# TMDB API
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

# Premium sozlamalari (Admin tomonidan o'zgartiriladi)
DEFAULT_PREMIUM_PRICES = {
    'week': 15000,    # 1 hafta - 15,000 so'm
    'month': 40000,   # 1 oy - 40,000 so'm
    'year': 350000    # 1 yil - 350,000 so'm
}

# To'lov ma'lumotlari (Admin tomonidan o'rnatiladi)
PAYMENT_CARD_INFO = {
    'card_number': '8600 0000 0000 0000',  # Admin kartasi
    'card_holder': 'ADMIN NOMI',
    'bank_name': 'Uzcard'
}

# Fayl yo'llari
DATA_DIR = "data"
MOVIES_DATA_FILE = os.path.join(DATA_DIR, "movies.json")
USERS_DATA_FILE = os.path.join(DATA_DIR, "users.json")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")
PREMIUM_PLANS_FILE = os.path.join(DATA_DIR, "premium_plans.json")
BROADCAST_HISTORY_FILE = os.path.join(DATA_DIR, "broadcast_history.json")

# Bot matnlari
START_MESSAGE = """🎬 <b>Kino Botga xush kelibsiz!</b>

🎯 <b>Bizning imkoniyatlarimiz:</b>
• 📱 Eng yangi va sifatli filmlar
• 🔍 Tez va oson qidiruv tizimi
• 📊 Film reytinglari va ma'lumotlari
• 🎭 Turli janrdagi filmlar

🔍 <b>Qidirish uchun:</b>
• Film nomini yozing
• Film kodini yuboring (masalan: 123)
• Yoki inline rejimda qidiring!

💎 <b>Premium obuna bilan:</b>
• Kanallarga a'zo bo'lmasdan foydalaning
• Reklamasiz tajriba
• Tezkor qidiruv

<i>Botdan foydalanish uchun majburiy kanallarga a'zo bo'ling yoki 💎 Premium obuna xarid qiling.</i>"""

MEMBERSHIP_REQUIRED_MESSAGE = """🛑 <b>Botdan foydalanish uchun quyidagi shartlardan birini bajaring:</b>

🎯 <b>1-usul: Kanallarga obuna</b>
📌 Quyidagi kanallarimizga obuna bo'ling:

{channels}

✅ So'ng "Obunani tekshirish" tugmasini bosing.

💎 <b>2-usul: Premium obuna</b>
• 🕐 1 hafta - {week_price:,} so'm
• 📅 1 oy - {month_price:,} so'm
• 🗓 1 yil - {year_price:,} so'm

<i>Premium obuna bilan kanallarga a'zo bo'lmasdan va reklamasiz botdan foydalaning!</i>"""

MOVIE_NOT_FOUND_FOR_USER = """❌ <b>Film topilmadi!</b>

🔍 <b>Qidiruv bo'yicha maslahatlar:</b>
• Film nomini to'liq yozing
• Inglizcha nomini sinab ko'ring
• Film kodini kiriting (masalan: 123)
• Yoki @{username} orqali inline qidiruv qiling

💡 <b>Masalan:</b> "Avengers", "123", "Spider-man"

🎬 Bizda ,5000+ sifatli filmlar mavjud!"""

MOVIE_NOT_FOUND_INLINE = "❌ Film topilmadi. Boshqa kalit so'zlar bilan qidiring."

PREMIUM_SUCCESS_MESSAGE = """🎉 <b>Premium obuna muvaffaqiyatli faollashtirildi!</b>

✅ <b>Sizning imkoniyatlaringiz:</b>
• 🚫 Kanallarga a'zo bo'lish majburiyati yo'q
• 🎯 Reklamasiz foydalanish
• ⚡ Tezkor qidiruv va yuklash
• 🆕 Eng yangi filmlar birinchi bo'lib

⏰ <b>Amal qilish muddati:</b> {expire_date}

💎 Premium obunangiz faol!"""

PAYMENT_INSTRUCTION_MESSAGE = """💳 <b>To'lov ma'lumotlari</b>

💰 <b>Summa:</b> {amount:,} so'm
⏰ <b>Muddat:</b> {duration}

💳 <b>Quyidagi karta raqamiga pul o'tkazing:</b>
<code>{card_number}</code>

👤 <b>Karta egasi:</b> {card_holder}
🏦 <b>Bank:</b> {bank_name}

📸 <b>To'lov qilgandan keyin:</b>
1. To'lov chekini screenshot qiling
2. Screenshot ni botga yuboring
3. Admin tasdiqidan keyin Premium faollashadi

⚠️ <b>Diqqat:</b> Faqat yuqoridagi karta raqamiga to'lov qiling!"""

# Keyboard tugmalari
KEYBOARD_TEXTS = {
    'search': '🔍 Film qidirish',
    'admin': '⚙️ Admin Panel',
    'back': '🔙 Orqaga',
    'premium': '💎 Premium',
    'channels': '📢 Kanallar',
    'check_subscription': '✅ Obunani tekshirish'
}

ADMIN_COMMANDS = {
    'add_video': '📹 Video qo\'shish',
    'stats': '📊 Statistika',
    'broadcast': '📢 Ommaviy xabar',
    'manage_channels': '📢 Kanallarni boshqarish',
    'premium_settings': '💎 Premium sozlamalar',
    'payment_requests': '💳 To\'lov so\'rovlari',
    'users_management': '👥 Foydalanuvchilar'
}

# To'lov holatlari
PAYMENT_STATUS = {
    'pending': 'pending',     # Kutilmoqda
    'approved': 'approved',   # Tasdiqlangan
    'rejected': 'rejected'    # Rad etilgan
}
