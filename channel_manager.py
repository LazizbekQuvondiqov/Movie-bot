# channel_manager.py
import logging
import json
from sqlalchemy.orm import Session
from database import Channel, Settings, SessionLocal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert # Fayl boshiga qo'shing


logger = logging.getLogger(__name__)

class ChannelManager:
    def __init__(self):
        self._init_settings()



    def _init_settings(self):
        """Boshlang'ich sozlamalarni yaratish (agar mavjud bo'lmasa)"""
        with SessionLocal() as db:
            try:
                # "INSERT ... ON CONFLICT DO NOTHING" SQL buyrug'ini ishlatamiz.
                # Bu "agar bunday yozuv bo'lmasa, qo'sh, agar bo'lsa, hech narsa qilma" degani.
                # Bu avval SELECT qilib, keyin INSERT qilishdan ko'ra ancha samarali.

                stmt = insert(Settings).values(
                    key="check_membership",
                    value="true"
                ).on_conflict_do_nothing(
                    index_elements=['key'] # Qaysi ustun bo'yicha takrorlanishni tekshirish
                )

                result = db.execute(stmt)
                db.commit()

                # result.rowcount > 0 bo'lsa, demak yangi yozuv qo'shildi.
                if result.rowcount > 0:
                    logger.info("check_membership sozlamasi yaratildi.")

            except Exception as e:
                db.rollback()
                logger.error(f"Boshlang'ich sozlamalarni yaratishda xatolik: {e}")
    def add_channel(self, channel_input: str):
        # Kiruvchi ma'lumotni tozalash
        try:
            username = channel_input.replace('https://t.me/', '').replace('@', '').strip().split('/')
            username = username[0] # Agar linkda qo'shimcha narsalar bo'lsa, faqat username'ni olamiz
            if not username or ' ' in username:
                return False, "Noto'g'ri kanal formati. Faqat @username yoki link yuboring."
        except Exception:
            return False, "Kanal formati tushunarsiz."

        with SessionLocal() as db:
            try:
                # Mavjudligini tekshirishning samarali usuli
                is_exists = db.query(db.query(Channel).filter(Channel.username == username).exists()).scalar()
                if is_exists:
                    return False, "Bu kanal allaqachon qo'shilgan."

                new_channel = Channel(
                    username=username,
                    url=f"https://t.me/{username}",
                    name=f"@{username}"
                )
                db.add(new_channel)
                db.commit()
                logger.info(f"Kanal qo'shildi: {username}")
                return True, f"✅ Kanal (@{username}) muvaffaqiyatli qo'shildi!"

            # Agar ikki admin bir vaqtda qo'shmoqchi bo'lsa va yuqoridagi tekshiruvdan o'tib ketsa,
            # bu xatolik kelib chiqadi. Bu shunday holatlar uchun himoya.
            except IntegrityError:
                db.rollback()
                logger.warning(f"Kanal allaqachon mavjud (IntegrityError): {username}")
                return False, "Bu kanal allaqachon qo'shilgan."

            except Exception as e:
                db.rollback()
                logger.error(f"Kanal qo'shishda xatolik: {e}")
                return False, "Ma'lumotlar bazasiga yozishda xatolik."
    def remove_channel(self, username: str):
        with SessionLocal() as db:
            try:
                # Bu yerda ham to'g'ridan-to'g'ri DELETE so'rovini bajaramiz.
                # Bu avval SELECT qilib, keyin DELETE qilishdan ko'ra tezroq.
                deleted_rows = db.query(Channel).filter(Channel.username == username).delete(
                    synchronize_session=False
                )
                db.commit()

                if deleted_rows > 0:
                    logger.info(f"Kanal o'chirildi: {username}")
                    return True, f"🗑 Kanal (@{username}) muvaffaqiyatli o'chirildi."
                else:
                    # Agar hech qanday qator o'chirilmagan bo'lsa, demak kanal topilmadi.
                    logger.warning(f"O'chirish uchun kanal topilmadi: {username}")
                    return False, "Kanal topilmadi."

            except Exception as e:
                db.rollback()
                logger.error(f"Kanal o'chirishda xatolik: {e}")
                return False, "Ma'lumotlar bazasidan o'chirishda xatolik."
    def get_all_channels(self):
        with SessionLocal() as db:
            try:
                # Kanallarni qo'shilgan sanasi bo'yicha tartiblash ro'yxatni chiroyliroq ko'rsatadi.
                return db.query(Channel).order_by(Channel.added_date).all()
            except Exception as e:
                logger.error(f"Barcha kanallar ro'yxatini olishda xatolik: {e}")
                return []

    def toggle_channel_status(self, username: str):
        with SessionLocal() as db:
            try:
                # .with_for_update() bir vaqtda ikki admin bitta kanalni o'zgartirishga harakat qilganda
                # yuzaga kelishi mumkin bo'lgan xatolikning oldini oladi.
                channel = db.query(Channel).filter(Channel.username == username).with_for_update().first()

                if not channel:
                    return False, "Kanal topilmadi."

                # Holatni o'zgartiramiz
                channel.is_active = not channel.is_active

                # Yangi holatni o'zgaruvchiga saqlab olamiz, chunki db.commit() dan keyin
                # obyektga murojaat qilish tavsiya etilmaydi.
                new_status_bool = channel.is_active

                db.commit()

                status_text = "✅ Faollashtirildi" if new_status_bool else "❌ Nofaollashtirildi"
                logger.info(f"Kanal holati o'zgartirildi: {username} - {status_text}")
                return True, f"Kanal (@{username}) holati o'zgartirildi: {status_text}"

            except Exception as e:
                db.rollback()
                logger.error(f"Kanal holatini o'zgartirishda xatolik: {e}")
                return False, "Ma'lumotlar bazasini yangilashda xatolik."
    def get_channel_list_for_check(self):
        with SessionLocal() as db:
            try:
                # is_active == True o'rniga shunchaki is_active yozish ham mumkin, bu SQLAlchemy'da qabul qilingan.
                return db.query(Channel).filter(Channel.is_active).all()
            except Exception as e:
                logger.error(f"Tekshirish uchun aktiv kanallar ro'yxatini olishda xatolik: {e}")
                return []
    def is_membership_required(self):
        with SessionLocal() as db:
            try:
                # .with_entities() faqat kerakli "value" ustunini oladi, bu tezroq.
                # .scalar() esa natijani to'g'ridan-to'g'ri (masalan, 'true') yoki None qaytaradi.
                setting_value = db.query(Settings.value).filter(Settings.key == "check_membership").scalar()

                # Agar sozlama topilmasa (None), standart holat "true" bo'ladi.
                if setting_value is None:
                    return True

                # Topilgan qiymatni tekshiramiz.
                return setting_value.lower() == 'true'

            except Exception as e:
                logger.error(f"A'zolik tekshiruvi sozlamasini olishda xatolik: {e}")
                # Xatolik yuz bersa, xavfsizlik uchun a'zolik talab qilinadi deb hisoblaymiz.
                return True

# channel_manager.py faylidagi FAQAT SHU FUNKSIYANI almashtiring

    def toggle_membership_check(self):
        with SessionLocal() as db:
            try:
                setting = db.query(Settings).filter(Settings.key == "check_membership").with_for_update().first()

                # Agar sozlama bazada yo'q bo'lsa (bu deyarli imkonsiz, lekin himoya uchun)
                if not setting:
                    # _init_settings() ni chaqiramiz, xuddi sizning eski kodingizdagidek.
                    self._init_settings()
                    # Va sozlamani qayta o'qiymiz
                    setting = db.query(Settings).filter(Settings.key == "check_membership").with_for_update().first()
                    if not setting:
                        raise Exception("check_membership sozlamasini yaratib bo'lmadi")

                current_status = setting.value.lower() == 'true'
                new_status = not current_status
                setting.value = str(new_status).lower()
                db.commit()

                status_text = "✅ Yoqildi" if new_status else "❌ O'chirildi"
                logger.info(f"A'zolik tekshiruvi {status_text}")
                return True, f"Majburiy a'zolik tekshiruvi {status_text}."
            except Exception as e:
                db.rollback()
                logger.error(f"A'zolik tekshiruvini o'zgartirishda xatolik: {e}")
                return False, "Sozlamani saqlashda xatolik."
