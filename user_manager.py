# user_manager.py (YAKUNIY VARIANT)

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from database import User, SessionLocal

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self):
        pass

    # get_db() funksiyasi olib tashlandi.

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        with SessionLocal() as db:
            try:
                # "INSERT ... ON CONFLICT DO UPDATE" dan foydalanamiz (upsert)
                # Bu bitta so'rovda ham qo'shish, ham yangilashni bajaradi.
                stmt = insert(User).values(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    last_seen=datetime.utcnow() # Har doim last_seen yangilanadi
                )

                update_stmt = stmt.on_conflict_do_update(
                    index_elements=['user_id'],
                    set_={
                        'username': stmt.excluded.username,
                        'first_name': stmt.excluded.first_name,
                        'last_name': stmt.excluded.last_name,
                        'last_seen': stmt.excluded.last_seen
                    }
                )

                db.execute(update_stmt)
                db.commit()
                # logger.info(f"Foydalanuvchi ma'lumotlari yangilandi/qo'shildi: {user_id}")
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"Foydalanuvchi qo'shish/yangilashda xatolik: {e}")
                return False

    def get_user(self, user_id: int):
        with SessionLocal() as db:
            try:
                return db.query(User).filter(User.user_id == user_id).first()
            except Exception as e:
                logger.error(f"Foydalanuvchi olishda xatolik: {e}")
                return None

    def increment_movie_watch(self, user_id: int):
        with SessionLocal() as db:
            try:
                # To'g'ridan-to'g'ri UPDATE so'rovi
                db.query(User).filter(User.user_id == user_id).update(
                    {User.movies_watched: User.movies_watched + 1},
                    synchronize_session=False
                )
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Film ko'rishni yangilashda xatolik: {e}")

    def is_banned(self, user_id: int):
        with SessionLocal() as db:
            try:
                # Faqat kerakli ustunni olamiz, bu ancha tez
                is_banned_status = db.query(User.is_banned).filter(User.user_id == user_id).scalar()
                return is_banned_status or False
            except Exception as e:
                logger.error(f"Ban statusini tekshirishda xatolik: {e}")
                return False # Xavfsizlik uchun, xatolik bo'lsa ban qilinmagan deb hisoblaymiz

    def get_all_user_ids(self):
        with SessionLocal() as db:
            try:
                user_ids = db.query(User.user_id).filter(User.is_banned == False).all()
                return [uid for (uid,) in user_ids]
            except Exception as e:
                logger.error(f"Barcha foydalanuvchi ID larini olishda xatolik: {e}")
                return []

    def get_user_stats(self):
        with SessionLocal() as db:
            try:
                # Statistikani bitta so'rovda olamiz
                stats_query = db.query(
                    func.count(User.user_id),
                    func.count(User.user_id).filter(User.is_banned == False)
                )
                total, active = stats_query.one()
                return {"total_users": total or 0, "active_users": active or 0}
            except Exception as e:
                logger.error(f"User statistikasida xatolik: {e}")
                return {"total_users": 0, "active_users": 0}

    def find_user(self, query: str):
        with SessionLocal() as db:
            try:
                query_str = str(query).lower().replace('@', '')

                # Bitta so'rovda ham ID, ham username bo'yicha qidiramiz
                user_query = db.query(User)
                if query_str.isdigit():
                    user_query = user_query.filter(User.user_id == int(query_str))
                else:
                    user_query = user_query.filter(func.lower(User.username) == query_str)

                return user_query.first()
            except Exception as e:
                logger.error(f"Foydalanuvchini topishda xatolik: {e}")
                return None
