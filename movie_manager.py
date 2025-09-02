# movie_manager.py
import json
import os
import logging
import time
from datetime import datetime
from threading import Lock
from config import MOVIES_DATA_FILE

logger = logging.getLogger(__name__)

class MovieManager:
    def __init__(self, file_path=MOVIES_DATA_FILE):
        self.movies_file = file_path
        self.lock = Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        try:
            os.makedirs(os.path.dirname(self.movies_file) or '.', exist_ok=True)
            if not os.path.exists(self.movies_file):
                initial_data = {"movies": {}}
                with open(self.movies_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Ma'lumotlar fayli yaratildi: {self.movies_file}")
        except PermissionError as e:
            logger.critical(f"RUXSATNOMA XATOSI: {self.movies_file} manzilida fayl/papka yaratib bo'lmadi. Ruxsatlarni tekshiring! Xato: {e}")
            raise
        except Exception as e:
            logger.critical(f"Fayl yaratishda kutilmagan xatolik: {e}")
            raise

    def _load_data(self):
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if not os.path.exists(self.movies_file) or os.path.getsize(self.movies_file) == 0:
                    logger.warning(f"Fayl topilmadi yoki bo'sh: {self.movies_file}. Yangisi yaratilmoqda.")
                    self._ensure_file_exists()
                    return {"movies": {}}

                with open(self.movies_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data.setdefault("movies", {})
                    return data

            except json.JSONDecodeError as e:
                logger.error(f"{self.movies_file} faylida JSON xatoligi (urinish {attempt+1}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                # Oxirgi urinishda backup yaratish
                backup_file = f"{self.movies_file}.corrupted_{int(datetime.now().timestamp())}"
                if os.path.exists(self.movies_file):
                    os.rename(self.movies_file, backup_file)
                    logger.info(f"Buzilgan fayl zaxiraga ko'chirildi: {backup_file}")
                self._ensure_file_exists()
                return {"movies": {}}
            except Exception as e:
                logger.error(f"Ma'lumotlarni yuklashda kutilmagan xatolik (urinish {attempt+1}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                raise

    def _save_data(self, data):
        max_attempts = 3
        for attempt in range(max_attempts):
            with self.lock:
                temp_file = f"{self.movies_file}.tmp"
                try:
                    # Ma'lumotlarni validatsiya qilish
                    if not isinstance(data, dict) or "movies" not in data:
                        logger.error("Noto'g'ri ma'lumot formati saqlashga urinildi")
                        return False

                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    # Atomik almashtirish
                    os.replace(temp_file, self.movies_file)
                    logger.debug(f"Ma'lumotlar muvaffaqiyatli saqlandi (urinish {attempt+1})")
                    return True

                except Exception as e:
                    logger.error(f"Ma'lumotlarni saqlashda xatolik (urinish {attempt+1}): {e}")
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
                    continue

        logger.critical("Ma'lumotlarni saqlashning barcha urinishlari muvaffaqiyatsiz!")
        return False

    def get_next_id(self):
        """
        Keyingi unikal ID ni mavjud filmlarning eng kattasiga qarab aniqlaydi.
        Bu usul ID larning ketma-ket (1, 2, 3...) bo'lishini ta'minlaydi.
        """
        try:
            data = self._load_data()
            movies = data.get("movies", {})

            if not movies:
                logger.info("Birinchi film qo'shilmoqda, ID: 1")
                return 1

            # Mavjud ID larni raqamga o'girib, eng kattasini topamiz
            existing_ids = []
            for k in movies.keys():
                try:
                    existing_ids.append(int(k))
                except ValueError:
                    logger.warning(f"Noto'g'ri ID format: {k}")
                    continue

            if not existing_ids:
                return 1

            next_id = max(existing_ids) + 1
            logger.info(f"Yangi ID yaratildi: {next_id}")
            return next_id

        except Exception as e:
            logger.error(f"ID olishda xatolik: {e}")
            return 1

    def add_movie(self, movie_id, movie_data):
        if not movie_id:
            logger.error("Noto'g'ri ID (None) bilan film qo'shib bo'lmaydi.")
            return False

        try:
            data = self._load_data()

            # Ma'lumotlarni tekshirish
            if not movie_data.get('file_id'):
                logger.error("file_id'siz film qo'shishga urinish.")
                return False

            # Zaruriy ma'lumotlarni qo'shish
            movie_data["added_date"] = datetime.now().isoformat()
            movie_data.setdefault("views", 0)
            movie_data.setdefault("title", "Noma'lum film")

            # Ma'lumotni qo'shish
            data["movies"][str(movie_id)] = movie_data

            # Eski `last_id` ni o'chirish (agar mavjud bo'lsa)
            if 'last_id' in data:
                del data['last_id']

            if self._save_data(data):
                movie_title = movie_data.get('title', 'Noma\'lum film')
                logger.info(f"Film muvaffaqiyatli qo'shildi: ID {movie_id}, Nomi: {movie_title}")
                return True
            else:
                logger.error(f"Film (ID: {movie_id}) qo'shilgandan so'ng ma'lumotlarni saqlashda xatolik.")
                return False

        except Exception as e:
            logger.error(f"Film qo'shishda kutilmagan xatolik: {e}", exc_info=True)
            return False

    def get_movie(self, movie_id):
        try:
            data = self._load_data()
            return data["movies"].get(str(movie_id))
        except Exception as e:
            logger.error(f"Film olishda xatolik (ID: {movie_id}): {e}")
            return None

    def update_views(self, movie_id):
        try:
            data = self._load_data()
            movie_id_str = str(movie_id)

            if movie_id_str in data["movies"]:
                current_views = data["movies"][movie_id_str].get("views", 0)
                data["movies"][movie_id_str]["views"] = current_views + 1

                if self._save_data(data):
                    new_views = data["movies"][movie_id_str]["views"]
                    logger.debug(f"Ko'rishlar soni yangilandi (Film ID: {movie_id}): {new_views}")
                    return new_views
                else:
                    logger.error(f"Ko'rishlar sonini saqlashda xatolik (Film ID: {movie_id})")
                    return current_views
            else:
                logger.warning(f"Film topilmadi views update uchun: ID {movie_id}")
            return 0
        except Exception as e:
            logger.error(f"Views update da xatolik: {e}")
            return 0

    def get_all_movies(self):
        try:
            data = self._load_data()
            movies = data.get("movies", {})

            # Sanaga qarab saralash
            sorted_movies = sorted(
                movies.items(),
                key=lambda item: item[1].get('added_date', '1970-01-01'),
                reverse=True
            )
            return dict(sorted_movies)
        except Exception as e:
            logger.error(f"Filmlarni olishda/saralashda xatolik: {e}")
            return {}

    def search_movies(self, query):
        try:
            query = query.lower().strip()
            all_movies = self.get_all_movies()

            if not query:
                return all_movies

            results = {}
            for movie_id, movie_data in all_movies.items():
                title = movie_data.get("title", "").lower()
                original_title = movie_data.get("original_title", "").lower()
                genres = [g.lower() for g in movie_data.get("genres", [])]

                if (query in title or
                    query in original_title or
                    query in " ".join(genres) or
                    query == str(movie_id)):
                    results[movie_id] = movie_data

            logger.debug(f"Qidiruv natijasi: {len(results)} film topildi")
            return results
        except Exception as e:
            logger.error(f"Qidirishda xatolik: {e}")
            return {}

    def get_stats(self):
        try:
            data = self._load_data()
            movies = data.get("movies", {})
            total_movies = len(movies)
            total_views = sum(movie.get("views", 0) for movie in movies.values())

            popular_movies = sorted(
                movies.items(),
                key=lambda movie: movie[1].get("views", 0),
                reverse=True
            )[:5]

            return {
                "total_movies": total_movies,
                "total_views": total_views,
                "popular_movies": popular_movies
            }
        except Exception as e:
            logger.error(f"Statistika olishda xatolik: {e}")
            return {"total_movies": 0, "total_views": 0, "popular_movies": []}

    def delete_movie(self, movie_id):
        try:
            data = self._load_data()
            movie_id_str = str(movie_id)

            if movie_id_str in data["movies"]:
                deleted_movie = data["movies"].pop(movie_id_str)
                if self._save_data(data):
                    deleted_title = deleted_movie.get('title', 'Noma\'lum film')
                    logger.info(f"Film o'chirildi: ID {movie_id}, Nomi: {deleted_title}")
                    return True
                else:
                    # Agar saqlashda xatolik bo'lsa, filmni qaytarib qo'yamiz
                    data["movies"][movie_id_str] = deleted_movie
                    return False
            else:
                logger.warning(f"O'chirish uchun film topilmadi: ID {movie_id}")
                return False
        except Exception as e:
            logger.error(f"Film o'chirishda xatolik (ID: {movie_id}): {e}")
            return False
