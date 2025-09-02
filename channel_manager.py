# channel_manager.py
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
                        "check_membership": True,
                        "premium_bypass": True
                    }
                }
                with open(self.channels_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Channels fayl yaratildi: {self.channels_file}")
        except Exception as e:
            logger.error(f"Channels fayl yaratishda xatolik: {e}")

    def _load_data(self):
        try:
            with open(self.channels_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault("channels", {})
                data.setdefault("settings", {"check_membership": True, "premium_bypass": True})
                return data
        except Exception as e:
            logger.error(f"Channels ma'lumot yuklashda xatolik: {e}")
            return {"channels": {}, "settings": {"check_membership": True, "premium_bypass": True}}

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

    def add_channel(self, channel_url, channel_name=None):
        """Kanal qo'shish"""
        try:
            # URL formatini tekshirish va tozalash
            if not channel_url.startswith('https://t.me/'):
                return False, "URL https://t.me/ bilan boshlanishi kerak"

            # Username olish
            username = channel_url.replace('https://t.me/', '').replace('@', '')
            if not username:
                return False, "Kanal username topilmadi"

            data = self._load_data()

            # Mavjudligini tekshirish
            if username in data["channels"]:
                return False, "Kanal allaqachon qo'shilgan"

            # Kanal ma'lumotlarini saqlash
            channel_data = {
                "username": username,
                "url": channel_url,
                "name": channel_name or username,
                "added_date": datetime.now().isoformat(),
                "is_active": True
            }

            data["channels"][username] = channel_data

            if self._save_data(data):
                logger.info(f"Kanal qo'shildi: {username}")
                return True, "Kanal muvaffaqiyatli qo'shildi"

            return False, "Ma'lumotlarni saqlashda xatolik"

        except Exception as e:
            logger.error(f"Kanal qo'shishda xatolik: {e}")
            return False, str(e)

    def remove_channel(self, username):
        """Kanalni o'chirish"""
        try:
            data = self._load_data()
            username = username.replace('@', '').replace('https://t.me/', '')

            if username not in data["channels"]:
                return False, "Kanal topilmadi"

            del data["channels"][username]

            if self._save_data(data):
                logger.info(f"Kanal o'chirildi: {username}")
                return True, "Kanal muvaffaqiyatli o'chirildi"

            return False, "Ma'lumotlarni saqlashda xatolik"

        except Exception as e:
            logger.error(f"Kanal o'chirishda xatolik: {e}")
            return False, str(e)

    def get_all_channels(self):
        """Barcha kanallarni olish"""
        try:
            data = self._load_data()
            return data.get("channels", {})
        except Exception as e:
            logger.error(f"Kanallarni olishda xatolik: {e}")
            return {}

    def get_active_channels(self):
        """Faol kanallarni olish"""
        try:
            data = self._load_data()
            channels = data.get("channels", {})
            active_channels = {}

            for username, channel_data in channels.items():
                if channel_data.get("is_active", True):
                    active_channels[username] = channel_data

            return active_channels
        except Exception as e:
            logger.error(f"Faol kanallarni olishda xatolik: {e}")
            return {}

    def toggle_channel_status(self, username):
        """Kanal holatini o'zgartirish (faol/nofaol)"""
        try:
            data = self._load_data()
            username = username.replace('@', '').replace('https://t.me/', '')

            if username not in data["channels"]:
                return False, "Kanal topilmadi"

            current_status = data["channels"][username].get("is_active", True)
            data["channels"][username]["is_active"] = not current_status

            if self._save_data(data):
                new_status = "faollashtirildi" if not current_status else "nofaollashtirildi"
                logger.info(f"Kanal {new_status}: {username}")
                return True, f"Kanal {new_status}"

            return False, "Ma'lumotlarni saqlashda xatolik"

        except Exception as e:
            logger.error(f"Kanal holatini o'zgartirishda xatolik: {e}")
            return False, str(e)

    def get_channel_list_for_check(self):
        """Tekshirish uchun kanallar ro'yxati"""
        try:
            active_channels = self.get_active_channels()
            channel_list = []

            for username, channel_data in active_channels.items():
                channel_list.append({
                    'username': username,
                    'url': channel_data['url'],
                    'name': channel_data.get('name', username)
                })

            return channel_list
        except Exception as e:
            logger.error(f"Tekshirish ro'yxatini olishda xatolik: {e}")
            return []

    def is_membership_required(self):
        """A'zolik tekshiruvi yoqilganligini tekshirish"""
        try:
            data = self._load_data()
            return data.get("settings", {}).get("check_membership", True)
        except Exception as e:
            logger.error(f"A'zolik sozlamasi tekshirishda xatolik: {e}")
            return True

    def toggle_membership_check(self):
        """A'zolik tekshiruvini yoqish/o'chirish"""
        try:
            data = self._load_data()
            current_status = data.get("settings", {}).get("check_membership", True)
            data["settings"]["check_membership"] = not current_status

            if self._save_data(data):
                new_status = "yoqildi" if not current_status else "o'chirildi"
                logger.info(f"A'zolik tekshiruvi {new_status}")
                return True, f"A'zolik tekshiruvi {new_status}"

            return False, "Sozlamani saqlashda xatolik"

        except Exception as e:
            logger.error(f"A'zolik tekshiruvini o'zgartirishda xatolik: {e}")
            return False, str(e)

    def get_settings(self):
        """Sozlamalarni olish"""
        try:
            data = self._load_data()
            return data.get("settings", {"check_membership": True, "premium_bypass": True})
        except Exception as e:
            logger.error(f"Sozlamalarni olishda xatolik: {e}")
            return {"check_membership": True, "premium_bypass": True}
