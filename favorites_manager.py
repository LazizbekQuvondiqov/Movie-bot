# favorites_manager.py (YANGI va TO'G'RI KOD)
import logging
from database import Favorite, SessionLocal

logger = logging.getLogger(__name__)

class FavoritesManager:
    def toggle_favorite(self, user_id: int, movie_id: int):
        """Kinoni sevimlilarga qo'shadi yoki olib tashlaydi."""
        with SessionLocal() as db:
            try:
                existing_fav = db.query(Favorite).filter_by(user_id=user_id, movie_id=movie_id).first()

                if existing_fav:
                    # Agar mavjud bo'lsa, o'chiramiz
                    db.delete(existing_fav)
                    db.commit()
                    logger.info(f"Foydalanuvchi {user_id} sevimlilaridan kinoni ({movie_id}) olib tashladi.")
                    return False # Olib tashlandi
                else:
                    # Agar yo'q bo'lsa, qo'shamiz
                    new_fav = Favorite(user_id=user_id, movie_id=movie_id)
                    db.add(new_fav)
                    db.commit()
                    logger.info(f"Foydalanuvchi {user_id} sevimlilariga kinoni ({movie_id}) qo'shdi.")
                    return True # Qo'shildi
            except Exception as e:
                db.rollback()
                logger.error(f"Sevimlilarni o'zgartirishda xatolik: {e}")
                raise e # Xatolikni yuqoriga uzatamiz, bu botda aniqroq xabar berishga yordam beradi

    def is_in_favorites(self, user_id: int, movie_id: int):
        """Kino sevimlilarda bor-yo'qligini tekshirish"""
        with SessionLocal() as db:
            try:
                # .exists() va .scalar() dan foydalanish .first() ga qaraganda samaraliroq
                is_exists = db.query(db.query(Favorite).filter_by(user_id=user_id, movie_id=movie_id).exists()).scalar()
                return is_exists
            except Exception as e:
                logger.error(f"Sevimlilarni tekshirishda xatolik: {e}")
                return False

# favorites_manager.py faylida FAQAT SHU FUNKSIYANI ALMASHTIRING

    def get_user_favorites(self, user_id: int):
        """Foydalanuvchining barcha sevimlilari ro'yxatini (kino IDlari) olish"""
        with SessionLocal() as db:
            try:
                # Klassik va 100% ishonchli usul:
                # Bu so'rov bazadan [(6,), (8,)] kabi natija qaytaradi
                favs_tuples = db.query(Favorite.movie_id).filter_by(user_id=user_id).order_by(Favorite.added_date.desc()).all()

                # Endi biz bu natijani oddiy ro'yxatga [6, 8] aylantiramiz
                return [fav[0] for fav in favs_tuples]

            except Exception as e:
                logger.error(f"Sevimlilar ro'yxatini olishda xatolik: {e}")
                return []
