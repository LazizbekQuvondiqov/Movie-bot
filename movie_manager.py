# movie_manager.py
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import Movie, SessionLocal

logger = logging.getLogger(__name__)

class MovieManager:
    def __init__(self):
        # Har bir operatsiya uchun yangi sessiya yaratamiz
        pass

    def get_db(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()



    def add_movie(self, movie_data: dict):
        """
        Yangi kinoni ma'lumotlar bazasiga qo'shish.
        movie_data lug'at (dictionary) bo'lishi kerak.
        """
        db: Session = next(self.get_db())
        try:
            # Yangi Movie obyektini yaratish
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
        except Exception as e:
            db.rollback()
            logger.error(f"Film qo'shishda xatolik: {e}", exc_info=True)
            return None

    def get_movie(self, movie_id: int):
        db: Session = next(self.get_db())
        try:
            movie = db.query(Movie).filter(Movie.id == movie_id).first()
            return movie
        except Exception as e:
            logger.error(f"Film olishda xatolik (ID: {movie_id}): {e}")
            return None

    def update_views(self, movie_id: int):
        db: Session = next(self.get_db())
        try:
            movie = db.query(Movie).filter(Movie.id == movie_id).first()
            if movie:
                movie.views = (movie.views or 0) + 1
                db.commit()
                logger.debug(f"Ko'rishlar soni yangilandi (Film ID: {movie_id}): {movie.views}")
                return movie.views
            return 0
        except Exception as e:
            db.rollback()
            logger.error(f"Views update da xatolik: {e}")
            return 0

    def get_all_movies(self, limit=50):
        db: Session = next(self.get_db())
        try:
            movies = db.query(Movie).order_by(desc(Movie.added_date)).limit(limit).all()
            return movies
        except Exception as e:
            logger.error(f"Barcha filmlarni olishda xatolik: {e}")
            return []

    def search_movies(self, query: str, limit=50):
        db: Session = next(self.get_db())
        try:
            query = query.lower().strip()
            if not query:
                return self.get_all_movies(limit=limit)

            # ID bo'yicha qidirish
            if query.isdigit():
                movie_by_id = db.query(Movie).filter(Movie.id == int(query)).first()
                if movie_by_id:
                    return [movie_by_id]

            # Matn bo'yicha qidirish
            search_filter = f"%{query}%"
            results = db.query(Movie).filter(
                (Movie.title.ilike(search_filter)) |
                (Movie.original_title.ilike(search_filter))
            ).order_by(desc(Movie.added_date)).limit(limit).all()

            logger.debug(f"Qidiruv natijasi: {len(results)} film topildi")
            return results
        except Exception as e:
            logger.error(f"Qidirishda xatolik: {e}")
            return []

    def get_stats(self):
        db: Session = next(self.get_db())
        try:
            total_movies = db.query(func.count(Movie.id)).scalar()
            total_views = db.query(func.sum(Movie.views)).scalar() or 0
            return {
                "total_movies": total_movies,
                "total_views": total_views,
            }
        except Exception as e:
            logger.error(f"Statistika olishda xatolik: {e}")
            return {"total_movies": 0, "total_views": 0}

    def delete_movie(self, movie_id: int):
        db: Session = next(self.get_db())
        try:
            movie = db.query(Movie).filter(Movie.id == movie_id).first()
            if movie:
                deleted_title = movie.title
                db.delete(movie)
                db.commit()
                logger.info(f"Film o'chirildi: ID {movie_id}, Nomi: {deleted_title}")
                return True, f"✅ '{deleted_title}' nomli kino (ID: {movie_id}) muvaffaqiyatli o'chirildi."
            else:
                return False, f"❌ ID si {movie_id} bo'lgan kino topilmadi."
        except Exception as e:
            db.rollback()
            logger.error(f"Film o'chirishda xatolik: {e}")
            return False, "❌ Kinoni o'chirishda kutilmagan xatolik yuz berdi."
    # Bu funksiyalarni MovieManager klassi ichiga qo'shing

    # delete_movie funksiyasidan keyin shu kodni qo'shing

    def get_top_movies(self, limit=10):
        """Eng ko'p ko'rilgan kinolarni olish"""
        db: Session = next(self.get_db())
        try:
            return db.query(Movie).order_by(desc(Movie.views)).limit(limit).all()
        except Exception as e:
            logger.error(f"Top kinolarni olishda xatolik: {e}")
            return []

    def get_latest_movies(self, limit=10):
        """Eng so'nggi qo'shilgan kinolarni olish"""
        db: Session = next(self.get_db())
        try:
            return db.query(Movie).order_by(desc(Movie.added_date)).limit(limit).all()
        except Exception as e:
            logger.error(f"Yangi kinolarni olishda xatolik: {e}")
            return []

    def get_all_genres(self):
        """Barcha unikal janrlarni olish"""
        db: Session = next(self.get_db())
        try:
            results = db.query(Movie.genres).filter(Movie.genres != None).distinct().all()
            all_genres = set()
            for (genre_str,) in results:
                if genre_str:
                    genres = [g.strip() for g in genre_str.split(',')]
                    all_genres.update(genres)
            return sorted(list(g for g in all_genres if g)) # Bo'sh janrlarni olib tashlash
        except Exception as e:
            logger.error(f"Janrlarni olishda xatolik: {e}")
            return []

    def get_movies_by_genre(self, genre_name, limit=10):
        """Ma'lum bir janrdagi kinolarni olish"""
        db: Session = next(self.get_db())
        try:
            search_filter = f"%{genre_name}%"
            return db.query(Movie).filter(Movie.genres.ilike(search_filter)).order_by(desc(Movie.views)).limit(limit).all()
        except Exception as e:
            logger.error(f"Janr bo'yicha kinolarni olishda xatolik: {e}")
            return []
