# movie_manager.py (YAKUNIY VARIANT)

import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from database import Movie, SessionLocal

logger = logging.getLogger(__name__)

class MovieManager:
    def __init__(self):
        pass


    def add_movie(self, movie_data: dict):
        """
        Yangi kinoni ma'lumotlar bazasiga qo'shish.
        """
        with SessionLocal() as db:
            try:
                # Agar bir xil file_id bilan film qo'shishga harakat qilinsa,
                # IntegrityError xatoligi yuz beradi.
                new_movie = Movie(
                    file_id=movie_data.get('file_id'),
                    title=movie_data.get('title'),
                    original_title=movie_data.get('original_title'),
                    year=movie_data.get('year'),
                    rating=movie_data.get('rating'),
                    poster_url=movie_data.get('poster_url'),
                    genres=movie_data.get('genres'),
                    countries=movie_data.get('countries'),
                    tmdb_id=movie_data.get('tmdb_id')
                )
                db.add(new_movie)
                db.commit()
                db.refresh(new_movie)
                logger.info(f"Film bazaga qo'shildi: ID {new_movie.id}, Nomi: {new_movie.title}")
                return new_movie.id
            except IntegrityError:
                db.rollback()
                logger.warning(f"Bu file_id ({movie_data.get('file_id')}) bilan film allaqachon mavjud.")
                # Mavjud filmni topib, uning ID sini qaytaramiz
                existing_movie = db.query(Movie.id).filter(Movie.file_id == movie_data.get('file_id')).scalar()
                return existing_movie
            except Exception as e:
                db.rollback()
                logger.error(f"Film qo'shishda xatolik: {e}", exc_info=True)
                return None

    def get_movie(self, movie_id: int):
        with SessionLocal() as db:
            try:
                return db.query(Movie).filter(Movie.id == movie_id).first()
            except Exception as e:
                logger.error(f"Film olishda xatolik (ID: {movie_id}): {e}")
                return None

    def get_movie_by_file_id(self, file_id: str):
        """Filmni unikal file_id bo'yicha bazadan qidirish"""
        with SessionLocal() as db:
            try:
                return db.query(Movie).filter(Movie.file_id == file_id).first()
            except Exception as e:
                logger.error(f"File ID bo'yicha film olishda xatolik: {e}")
                return None

    def update_views(self, movie_id: int):
        with SessionLocal() as db:
            try:
                # To'g'ridan-to'g'ri UPDATE so'rovi - bu ancha tezroq
                result = db.query(Movie).filter(Movie.id == movie_id).update(
                    {Movie.views: Movie.views + 1},
                    synchronize_session=False
                )
                db.commit()
                if result > 0:
                    # Yangi qiymatni bilish shart bo'lsa, uni alohida so'rov bilan olamiz.
                    # Lekin ko'pincha bu shart emas. Agar kerak bo'lsa, quyidagi qatorni oching.
                    # new_views = db.query(Movie.views).filter(Movie.id == movie_id).scalar()
                    # return new_views
                    return True # Muvaffaqiyatli yangilanganini bildiradi
                return False
            except Exception as e:
                db.rollback()
                logger.error(f"Ko'rishlar sonini yangilashda xatolik: {e}")
                return False

    def get_all_movies(self, limit=50):
        with SessionLocal() as db:
            try:
                return db.query(Movie).order_by(desc(Movie.added_date)).limit(limit).all()
            except Exception as e:
                logger.error(f"Barcha filmlarni olishda xatolik: {e}")
                return []

    def search_movies(self, query: str, limit: int = 50, offset: int = 0):
        with SessionLocal() as db:
            try:
                query = query.lower().strip()
                search_query = db.query(Movie)

                if query.isdigit() and offset == 0:
                    movie_by_id = search_query.filter(Movie.id == int(query)).first()
                    if movie_by_id:
                        return [movie_by_id]

                if query:
                    search_filter = f"%{query}%"
                    search_query = search_query.filter(
                        (Movie.title.ilike(search_filter)) |
                        (Movie.original_title.ilike(search_filter))
                    )

                results = search_query.order_by(desc(Movie.added_date)).offset(offset).limit(limit).all()
                logger.debug(f"Qidiruv natijasi: {len(results)} film topildi (so'rov: '{query}', offset: {offset})")
                return results
            except Exception as e:
                logger.error(f"Qidirishda xatolik: {e}")
                return []

    def get_stats(self):
        with SessionLocal() as db:
            try:
                total_movies = db.query(func.count(Movie.id)).scalar()
                total_views = db.query(func.sum(Movie.views)).scalar() or 0
                return {"total_movies": total_movies, "total_views": total_views}
            except Exception as e:
                logger.error(f"Statistika olishda xatolik: {e}")
                return {"total_movies": 0, "total_views": 0}

    def delete_movie(self, movie_id: int):
        with SessionLocal() as db:
            try:
                # O'chirishdan oldin nomini olib olamiz
                movie_title = db.query(Movie.title).filter(Movie.id == movie_id).scalar()
                if not movie_title:
                    return False, f"❌ ID si {movie_id} bo'lgan kino topilmadi."

                # To'g'ridan-to'g'ri DELETE so'rovi
                db.query(Movie).filter(Movie.id == movie_id).delete(synchronize_session=False)
                db.commit()

                logger.info(f"Film o'chirildi: ID {movie_id}, Nomi: {movie_title}")
                return True, f"✅ '{movie_title}' nomli kino (ID: {movie_id}) muvaffaqiyatli o'chirildi."
            except Exception as e:
                db.rollback()
                logger.error(f"Film o'chirishda xatolik: {e}")
                return False, "❌ Kinoni o'chirishda kutilmagan xatolik yuz berdi."

    def get_top_movies(self, limit=10):
        with SessionLocal() as db:
            try:
                return db.query(Movie).order_by(desc(Movie.views)).limit(limit).all()
            except Exception as e:
                logger.error(f"Top kinolarni olishda xatolik: {e}")
                return []

    def get_latest_movies(self, limit=10):
        with SessionLocal() as db:
            try:
                return db.query(Movie).order_by(desc(Movie.added_date)).limit(limit).all()
            except Exception as e:
                logger.error(f"Yangi kinolarni olishda xatolik: {e}")
                return []

    def get_all_genres(self):
        with SessionLocal() as db:
            try:
                results = db.query(Movie.genres).filter(Movie.genres != None).distinct().all()
                all_genres = set()
                for (genre_str,) in results:
                    if genre_str:
                        genres = [g.strip() for g in genre_str.split(',')]
                        all_genres.update(g for g in genres if g) # Bo'sh janrlarni o'tkazib yuborish
                return sorted(list(all_genres))
            except Exception as e:
                logger.error(f"Janrlarni olishda xatolik: {e}")
                return []

    def get_movies_by_genre(self, genre_name, limit=10):
        with SessionLocal() as db:
            try:
                search_filter = f"%{genre_name}%"
                return db.query(Movie).filter(Movie.genres.ilike(search_filter)).order_by(desc(Movie.views)).limit(limit).all()
            except Exception as e:
                logger.error(f"Janr bo'yicha kinolarni olishda xatolik: {e}")
                return []
