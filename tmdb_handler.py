# tmdb_handler.py
import requests
import logging
import time
from config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE_URL
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

class TMDBHandler:
    def __init__(self):
        self.api_key = TMDB_API_KEY
        self.base_url = TMDB_BASE_URL
        self.image_base_url = TMDB_IMAGE_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json',
            'User-Agent': 'KinoBot/3.0'
        })
        self.last_request_time = 0
        self.min_request_interval = 0.5

    def _wait_if_needed(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def parse_caption(self, caption):
        if not caption:
            return "", [], []
        movie_name = caption.split('\n')[0].strip()
        return movie_name, [], []

    def search_movie(self, movie_name):
        """O'zbekcha va inglizcha qidirish"""
        if not movie_name or not self.api_key:
            return []

        # 1-qadam: O'zbekcha qidirib ko'rish
        logger.info(f"TMDB'dan qidirilmoqda (uz): '{movie_name}'")
        results = self._perform_search(movie_name)

        # 2-qadam: Agar natija bo'lmasa, inglizchaga tarjima qilib qidirish
        if not results:
            try:
                logger.info(f"O'zbekcha natija topilmadi. Inglizchaga tarjima qilinmoqda...")
                translated_name = GoogleTranslator(source='auto', target='en').translate(movie_name)
                if translated_name and translated_name.lower() != movie_name.lower():
                    logger.info(f"TMDB'dan qidirilmoqda (en): '{translated_name}'")
                    results = self._perform_search(translated_name)
                else:
                    logger.warning("Tarjima qilishda xatolik yoki nom o'zgarmadi.")
            except Exception as e:
                logger.error(f"'{movie_name}' nomini tarjima qilishda xatolik: {e}")

        return results

    def _perform_search(self, query):
        try:
            self._wait_if_needed()
            url = f"{self.base_url}/search/movie"
            params = {
                'api_key': self.api_key,
                'query': query.strip(),
                'language': 'en-US' # Ma'lumotlarni inglizcha olamiz, chunki to'liqroq
            }
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            results = data.get('results', [])[:5] # Eng yaxshi 5 ta natija
            logger.info(f"'{query}' uchun {len(results)} ta natija topildi.")
            return results
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB qidiruv xatoligi: {e}")
            return []

    def get_movie_details(self, tmdb_id):
        if not tmdb_id or not self.api_key:
            return None
        try:
            self._wait_if_needed()
            url = f"{self.base_url}/movie/{tmdb_id}"
            params = {'api_key': self.api_key, 'language': 'en-US'}
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            return {
                "original_title": data.get('title', ''),
                "year": data.get('release_date', '')[:4] if data.get('release_date') else '',
                "rating": round(data.get('vote_average', 0), 1),
                "poster_url": f"{self.image_base_url}{data['poster_path']}" if data.get('poster_path') else None,
                "tmdb_id": data.get('id'),
                "genres": ", ".join([g['name'] for g in data.get('genres', [])]),
                "countries": ", ".join([c['name'] for c in data.get('production_countries', [])]),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB ma'lumot olish xatoligi (ID: {tmdb_id}): {e}")
            return None
