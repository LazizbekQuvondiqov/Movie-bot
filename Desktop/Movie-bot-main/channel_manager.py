# channel_manager.py
import logging
import json
from sqlalchemy.orm import Session
from database import Channel, Settings, SessionLocal

logger = logging.getLogger(__name__)

class ChannelManager:
    def __init__(self):
        self._init_settings()

    def get_db(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _init_settings(self):
        """Boshlang'ich sozlamalarni yaratish (agar mavjud bo'lmasa)"""
        db: Session = next(self.get_db())
        try:
            # Majburiy a'zolik
            membership_check = db.query(Settings).filter(Settings.key == "check_membership").first()
            if not membership_check:
                new_setting = Settings(key="check_membership", value="true")
                db.add(new_setting)
                db.commit()
                logger.info("check_membership sozlamasi yaratildi.")
        except Exception as e:
            db.rollback()
            logger.error(f"Boshlang'ich sozlamalarni yaratishda xatolik: {e}")

    def add_channel(self, channel_input: str):
        db: Session = next(self.get_db())
        try:
            username = channel_input.replace('https://t.me/', '').replace('@', '').strip()
            if not username or ' ' in username:
                return False, "Noto'g'ri kanal formati. Faqat @username yoki link yuboring."

            existing_channel = db.query(Channel).filter(Channel.username == username).first()
            if existing_channel:
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
        except Exception as e:
            db.rollback()
            logger.error(f"Kanal qo'shishda xatolik: {e}")
            return False, "Ma'lumotlar bazasiga yozishda xatolik."

    def remove_channel(self, username: str):
        db: Session = next(self.get_db())
        try:
            channel = db.query(Channel).filter(Channel.username == username).first()
            if not channel:
                return False, "Kanal topilmadi."

            db.delete(channel)
            db.commit()
            logger.info(f"Kanal o'chirildi: {username}")
            return True, f"🗑 Kanal (@{username}) muvaffaqiyatli o'chirildi."
        except Exception as e:
            db.rollback()
            logger.error(f"Kanal o'chirishda xatolik: {e}")
            return False, "Ma'lumotlar bazasidan o'chirishda xatolik."

    def get_all_channels(self):
        db: Session = next(self.get_db())
        try:
            return db.query(Channel).all()
        except Exception as e:
            logger.error(f"Kanallarni olishda xatolik: {e}")
            return []

    def toggle_channel_status(self, username: str):
        db: Session = next(self.get_db())
        try:
            channel = db.query(Channel).filter(Channel.username == username).first()
            if not channel:
                return False, "Kanal topilmadi."

            channel.is_active = not channel.is_active
            db.commit()

            status_text = "✅ Faollashtirildi" if channel.is_active else "❌ Nofaollashtirildi"
            logger.info(f"Kanal holati o'zgartirildi: {username} - {status_text}")
            return True, f"Kanal (@{username}) holati o'zgartirildi: {status_text}"
        except Exception as e:
            db.rollback()
            logger.error(f"Kanal holatini o'zgartirishda xatolik: {e}")
            return False, "Ma'lumotlar bazasini yangilashda xatolik."

    def get_channel_list_for_check(self):
        db: Session = next(self.get_db())
        try:
            return db.query(Channel).filter(Channel.is_active == True).all()
        except Exception as e:
            logger.error(f"Tekshirish ro'yxatini olishda xatolik: {e}")
            return []

    def is_membership_required(self):
        db: Session = next(self.get_db())
        try:
            setting = db.query(Settings).filter(Settings.key == "check_membership").first()
            return setting.value.lower() == 'true' if setting else True
        except Exception as e:
            logger.error(f"A'zolik tekshiruvi sozlamasini olishda xatolik: {e}")
            return True

    def toggle_membership_check(self):
        db: Session = next(self.get_db())
        try:
            setting = db.query(Settings).filter(Settings.key == "check_membership").first()
            if not setting:
                self._init_settings() # Agar yo'q bo'lsa, yaratib olamiz
                setting = db.query(Settings).filter(Settings.key == "check_membership").first()

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
