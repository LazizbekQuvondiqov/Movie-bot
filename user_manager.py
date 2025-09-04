import json
import os
import logging
from datetime import datetime, timedelta
from threading import Lock
from config import USERS_DATA_FILE, DATA_DIR

logger = logging.getLogger(__name__)

class UserManager:
    # >>>>>>>>>>>>>>>>>>>> 3-TUZATISH: __init__ o'zgartirildi <<<<<<<<<<<<<<<<<<<<<<<
    def __init__(self, payment_manager):
        self.users_file = USERS_DATA_FILE
        self.lock = Lock()
        self.payment_manager = payment_manager
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(self.users_file):
                initial_data = {"users": {}}
                with open(self.users_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Users fayl yaratildi: {self.users_file}")
        except Exception as e:
            logger.error(f"Users fayl yaratishda xatolik: {e}")

    def _load_data(self):
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault("users", {})
                return data
        except Exception as e:
            logger.error(f"Users ma'lumot yuklashda xatolik: {e}")
            return {"users": {}}

    def _save_data(self, data):
        with self.lock:
            try:
                temp_file = f"{self.users_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.users_file)
                return True
            except Exception as e:
                logger.error(f"Users ma'lumot saqlashda xatolik: {e}")
                return False

    def add_user(self, user_id, username=None, first_name=None, last_name=None):
        """Yangi foydalanuvchi qo'shish yoki mavjudini yangilash"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                user_data = data["users"][user_id_str]
                user_data["username"] = username
                user_data["first_name"] = first_name
                user_data["last_name"] = last_name
                user_data["last_seen"] = datetime.now().isoformat()
                is_new = False
            else:
                user_data = {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "joined_date": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat(),
                    "is_banned": False,
                    "message_count": 0,
                    "movies_watched": 0
                }
                data["users"][user_id_str] = user_data
                is_new = True
            if self._save_data(data):
                action_text = "qo'shildi" if is_new else "yangilandi"
                logger.info(f"Foydalanuvchi {action_text}: {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Foydalanuvchi qo'shishda xatolik: {e}")
            return False

    def get_user(self, user_id):
        """Foydalanuvchi ma'lumotlarini olish"""
        try:
            data = self._load_data()
            return data["users"].get(str(user_id))
        except Exception as e:
            logger.error(f"Foydalanuvchi olishda xatolik: {e}")
            return None

    def update_user_activity(self, user_id):
        """Foydalanuvchi faolligini yangilash"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                data["users"][user_id_str]["last_seen"] = datetime.now().isoformat()
                data["users"][user_id_str]["message_count"] = data["users"][user_id_str].get("message_count", 0) + 1
                self._save_data(data)
        except Exception as e:
            logger.error(f"Faollik yangilashda xatolik: {e}")

    def increment_movie_watch(self, user_id):
        """Ko'rilgan filmlar sonini oshirish"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                data["users"][user_id_str]["movies_watched"] = data["users"][user_id_str].get("movies_watched", 0) + 1
                self._save_data(data)
        except Exception as e:
            logger.error(f"Film ko'rish yangilashda xatolik: {e}")

    def ban_user(self, user_id, admin_id):
        """Foydalanuvchini bloklash"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                data["users"][user_id_str]["is_banned"] = True
                data["users"][user_id_str]["banned_by"] = admin_id
                data["users"][user_id_str]["banned_date"] = datetime.now().isoformat()
                if self._save_data(data):
                    logger.info(f"Foydalanuvchi bloklandi: {user_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Bloklashda xatolik: {e}")
            return False

    def unban_user(self, user_id, admin_id):
        """Foydalanuvchi blokini yechish"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                data["users"][user_id_str]["is_banned"] = False
                data["users"][user_id_str]["unbanned_by"] = admin_id
                data["users"][user_id_str]["unbanned_date"] = datetime.now().isoformat()
                if self._save_data(data):
                    logger.info(f"Foydalanuvchi bloki yechildi: {user_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Blok yechishda xatolik: {e}")
            return False

    def is_banned(self, user_id):
        """Foydalanuvchi bloklanganligini tekshirish"""
        try:
            user = self.get_user(user_id)
            return user.get("is_banned", False) if user else False
        except Exception as e:
            logger.error(f"Blok tekshirishda xatolik: {e}")
            return False

    def get_all_users(self):
        """Barcha foydalanuvchilarni olish"""
        try:
            data = self._load_data()
            return data.get("users", {})
        except Exception as e:
            logger.error(f"Barcha foydalanuvchilarni olishda xatolik: {e}")
            return {}

    def get_user_stats(self):
        """Foydalanuvchi statistikasi"""
        try:
            data = self._load_data()
            users = data.get("users", {})
            total_users = len(users)
            active_users = sum(1 for user in users.values() if not user.get("is_banned", False))
            banned_users = sum(1 for user in users.values() if user.get("is_banned", False))
            premium_users_count = 0
            for user_id_str in users.keys():
                if self.payment_manager.is_premium_user(int(user_id_str)):
                    premium_users_count += 1
            yesterday = datetime.now() - timedelta(days=1)
            daily_active = 0
            for user in users.values():
                try:
                    last_seen = datetime.fromisoformat(user.get("last_seen", "1970-01-01"))
                    if last_seen > yesterday:
                        daily_active += 1
                except:
                    pass
            return {
                "total_users": total_users,
                "active_users": active_users,
                "banned_users": banned_users,
                "premium_users": premium_users_count,
                "daily_active": daily_active
            }
        except Exception as e:
            logger.error(f"User statistikasida xatolik: {e}")
            return {}

    # >>>>>>>>>>>>>>>>>>>> 3-TUZATISH: get_users_for_broadcast o'zgartirildi <<<<<<<<<<<<<<<<<<<<<<<
    def get_users_for_broadcast(self):
        """Ommaviy xabar uchun (premium bo'lmagan) foydalanuvchilar ro'yxati"""
        try:
            data = self._load_data()
            users = data.get("users", {})
            target_users = []
            for user_id_str, user_data in users.items():
                user_id = int(user_id_str)
                if not user_data.get("is_banned", False) and not self.payment_manager.is_premium_user(user_id):
                    target_users.append(user_id)
            logger.info(f"Ommaviy xabar uchun {len(target_users)} ta foydalanuvchi topildi.")
            return target_users
        except Exception as e:
            logger.error(f"Broadcast foydalanuvchilarni olishda xatolik: {e}")
            return []
    def find_user(self, query):
        """Foydalanuvchini ID yoki username bo'yicha topish"""
        try:
            users = self.get_all_users()
            query = str(query).lower().replace('@', '')

            # Avval ID bo'yicha qidiramiz
            if query.isdigit() and query in users:
                return users[query]

            # Keyin username bo'yicha qidiramiz
            for user_data in users.values():
                if user_data.get('username') and user_data['username'].lower() == query:
                    return user_data

            return None # Agar topilmasa
        except Exception as e:
            logger.error(f"Foydalanuvchini topishda xatolik: {e}")
            return None
