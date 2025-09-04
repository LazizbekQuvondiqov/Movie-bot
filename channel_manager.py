import json
import os
import logging
from datetime import datetime
from threading import Lock
from config import CHANNELS_FILE, DATA_DIR

logger = logging.getLogger(__name__)

class ChannelManager:
    def __init__(self):
        self.channels_file = CHANNELS_FILE
        self.lock = Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(self.channels_file):
                initial_data = {
                    "channels": {},
                    "settings": {
                        "check_membership": True
                    }
                }
                with open(self.channels_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Channels fayl yaratildi: {self.channels_file}")
        except Exception as e:
            logger.error(f"Channels fayl yaratishda xatolik: {e}")

    def _load_data(self):
        try:
            with self.lock:
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data.setdefault("channels", {})
                    data.setdefault("settings", {"check_membership": True})
                    return data
        except Exception as e:
            logger.error(f"Channels ma'lumot yuklashda xatolik: {e}")
            return {"channels": {}, "settings": {"check_membership": True}}

    def _save_data(self, data):
        with self.lock:
            try:
                temp_file = f"{self.channels_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.channels_file)
                return True
            except Exception as e:
                logger.error(f"Channels ma'lumot saqlashda xatolik: {e}")
                return False

    def add_channel(self, channel_input):
        """Kanal qo'shish (username yoki link orqali)"""
        try:
            username = channel_input.replace('https://t.me/', '').replace('@', '').strip()
            if not username or ' ' in username:
                return False, "Noto'g'ri kanal formati. Faqat @username yoki link yuboring."

            data = self._load_data()

            if username in data["channels"]:
                return False, "Bu kanal allaqachon qo'shilgan."

            channel_data = {
                "username": username,
                "url": f"https://t.me/{username}",
                "name": f"@{username}", # Boshlang'ich nom
                "added_date": datetime.now().isoformat(),
                "is_active": True
            }
            data["channels"][username] = channel_data

            if self._save_data(data):
                logger.info(f"Kanal qo'shildi: {username}")
                return True, f"✅ Kanal (@{username}) muvaffaqiyatli qo'shildi!"
            return False, "Ma'lumotlarni saqlashda xatolik."
        except Exception as e:
            logger.error(f"Kanal qo'shishda xatolik: {e}")
            return False, str(e)

    def remove_channel(self, username):
        """Kanalni o'chirish"""
        try:
            data = self._load_data()
            if username not in data["channels"]:
                return False, "Kanal topilmadi."

            del data["channels"][username]
            if self._save_data(data):
                logger.info(f"Kanal o'chirildi: {username}")
                return True, f"🗑 Kanal (@{username}) muvaffaqiyatli o'chirildi."
            return False, "Ma'lumotlarni saqlashda xatolik."
        except Exception as e:
            logger.error(f"Kanal o'chirishda xatolik: {e}")
            return False, str(e)

    def get_all_channels(self):
        """Barcha kanallarni olish"""
        return self._load_data().get("channels", {})

    def toggle_channel_status(self, username):
        """Kanal holatini o'zgartirish (faol/nofaol)"""
        try:
            data = self._load_data()
            if username not in data["channels"]:
                return False, "Kanal topilmadi."

            current_status = data["channels"][username].get("is_active", True)
            new_status = not current_status
            data["channels"][username]["is_active"] = new_status

            if self._save_data(data):
                status_text = "✅ Faollashtirildi" if new_status else "❌ Nofaollashtirildi"
                logger.info(f"Kanal holati o'zgartirildi: {username} - {status_text}")
                return True, f"Kanal (@{username}) holati o'zgartirildi: {status_text}"
            return False, "Ma'lumotlarni saqlashda xatolik."
        except Exception as e:
            logger.error(f"Kanal holatini o'zgartirishda xatolik: {e}")
            return False, str(e)

    def get_channel_list_for_check(self):
        """Tekshirish uchun faol kanallar ro'yxati"""
        try:
            all_channels = self.get_all_channels()
            active_channels = []
            for channel_data in all_channels.values():
                if channel_data.get("is_active", True):
                    active_channels.append(channel_data)
            return active_channels
        except Exception as e:
            logger.error(f"Tekshirish ro'yxatini olishda xatolik: {e}")
            return []

    def is_membership_required(self):
        """A'zolik tekshiruvi yoqilganligini tekshirish"""
        return self._load_data().get("settings", {}).get("check_membership", True)

    def toggle_membership_check(self):
        """A'zolik tekshiruvini yoqish/o'chirish"""
        try:
            data = self._load_data()
            current_status = data.get("settings", {}).get("check_membership", True)
            new_status = not current_status
            data["settings"]["check_membership"] = new_status
            if self._save_data(data):
                status_text = "✅ Yoqildi" if new_status else "❌ O'chirildi"
                logger.info(f"A'zolik tekshiruvi {status_text}")
                return True, f"Majburiy a'zolik tekshiruvi {status_text}."
            return False, "Sozlamani saqlashda xatolik."
        except Exception as e:
            logger.error(f"A'zolik tekshiruvini o'zgartirishda xatolik: {e}")
            return False, str(e)
