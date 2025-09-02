# tmdb_handler.py - Sekinlashtirilgan versiya
import requests
import logging
from config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE_URL
import time

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
        # Rate limiting uchun
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 soniya kutish

    def _wait_if_needed(self):
        """So'rov yuborishdan oldin kerakli vaqt kutish"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limit: {sleep_time:.1f} soniya kutilmoqda")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def parse_caption(self, caption):
        if not caption:
            return "", [], []
        movie_name = caption.split('\n')[0].strip()
        return movie_name, [], []

    def search_movie(self, movie_name):
        """Sekinlashtirilgan qidiruv"""
        if not movie_name or not self.api_key:
            return []

        try:
            self._wait_if_needed()  # Rate limiting

            url = f"{self.base_url}/search/movie"
            params = {
                'api_key': self.api_key,
                'query': movie_name.strip(),
                'language': 'en-US'
            }

            logger.debug(f"TMDB search so'rovi: {movie_name}")
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])[:10]
            logger.info(f"TMDB search natija: {len(results)} film topildi")

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB search xatoligi: {e}")
            return []

    def get_movie_details(self, tmdb_id):
        """Sekinlashtirilgan ma'lumot olish"""
        if not tmdb_id or not self.api_key:
            logger.error(f"TMDB ID yoki API kaliti mavjud emas: tmdb_id={tmdb_id}")
            return None

        for attempt in range(3):  # 3 marta qayta urinish
            try:
                self._wait_if_needed()  # Rate limiting

                url = f"{self.base_url}/movie/{tmdb_id}"
                params = {
                    'api_key': self.api_key,
                    'language': 'en-US',
                    'append_to_response': 'credits'
                }

                logger.debug(f"TMDB details so'rovi (Urinish {attempt+1}/3): ID={tmdb_id}")
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()

                movie_details = {
                    "original_title": data.get('title', ''),
                    "overview": data.get('overview', ''),
                    "year": data.get('release_date', '')[:4] if data.get('release_date') else '',
                    "rating": round(data.get('vote_average', 0), 1),
                    "poster_url": f"{self.image_base_url}{data['poster_path']}" if data.get('poster_path') else None,
                    "tmdb_id": data.get('id'),
                    "genres": [g['name'] for g in data.get('genres', [])],
                    "countries": [c['name'] for c in data.get('production_countries', [])],
                }

                logger.info(f"TMDB'dan ma'lumot muvaffaqiyatli olindi: ID {tmdb_id}, Nomi: {movie_details['original_title']}")
                return movie_details

            except requests.exceptions.RequestException as e:
                logger.error(f"TMDB details xatoligi (Urinish {attempt+1}/3): ID={tmdb_id}, Xato: {e}")
                if attempt < 2:
                    wait_time = (attempt + 1) * 2  # 2, 4 soniya kutish
                    logger.info(f"Qayta urinishdan oldin {wait_time} soniya kutilmoqda...")
                    time.sleep(wait_time)
                continue

        logger.critical(f"TMDB'dan ma'lumot olishning barcha urinishlari muvaffaqiyatsiz: ID={tmdb_id}")
        return None
