# favorites_manager.py
import json
import os
import logging
from threading import Lock
from config import DATA_DIR # config.py dan DATA_DIR ni import qilamiz

logger = logging.getLogger(__name__)

# Fayl yo'lini aniqlash
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")

class FavoritesManager:
    def __init__(self):
        self.file_path = FAVORITES_FILE
        self.lock = Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Fayl mavjudligini tekshirish va kerak bo'lsa yaratish"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(self.file_path):
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f) # Boshlang'ich ma'lumot - bo'sh lug'at
                logger.info(f"Sevimlilar fayli yaratildi: {self.file_path}")
        except Exception as e:
            logger.error(f"Sevimlilar faylini yaratishda xatolik: {e}")

    def _load_data(self):
        """Fayldan ma'lumotlarni o'qish"""
        with self.lock:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {} # Agar fayl bo'sh yoki xato bo'lsa, bo'sh lug'at qaytaramiz

    def _save_data(self, data):
        """Ma'lumotlarni faylga saqlash"""
        with self.lock:
            try:
                temp_file = f"{self.file_path}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, self.file_path)
                return True
            except Exception as e:
                logger.error(f"Sevimlilar ma'lumotini saqlashda xatolik: {e}")
                return False

    def toggle_favorite(self, user_id, movie_id):
        """
        Kinoni sevimlilarga qo'shadi yoki olib tashlaydi.
        Returns: True (qo'shildi), False (olib tashlandi).
        """
        user_id_str = str(user_id)
        movie_id_int = int(movie_id)

        data = self._load_data()

        # Foydalanuvchi uchun ro'yxatni olish yoki yaratish
        user_favorites = data.get(user_id_str, [])

        if movie_id_int in user_favorites:
            # Agar kino allaqachon sevimlilarda bo'lsa, olib tashlaymiz
            user_favorites.remove(movie_id_int)
            action_is_add = False
            logger.info(f"Foydalanuvchi {user_id} sevimlilaridan kinoni ({movie_id}) olib tashladi.")
        else:
            # Aks holda, qo'shamiz
            user_favorites.append(movie_id_int)
            action_is_add = True
            logger.info(f"Foydalanuvchi {user_id} sevimlilariga kinoni ({movie_id}) qo'shdi.")

        data[user_id_str] = user_favorites
        self._save_data(data)
        return action_is_add

    def is_in_favorites(self, user_id, movie_id):
        """Kino sevimlilarda bor-yo'qligini tekshirish"""
        user_id_str = str(user_id)
        movie_id_int = int(movie_id)

        data = self._load_data()
        return movie_id_int in data.get(user_id_str, [])

    def get_user_favorites(self, user_id):
        """Foydalanuvchining barcha sevimlilari ro'yxatini (kino IDlari) olish"""
        user_id_str = str(user_id)
        data = self._load_data()
        return data.get(user_id_str, [])
