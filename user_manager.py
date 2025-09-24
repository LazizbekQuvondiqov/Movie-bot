# user_manager.py
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import User, SessionLocal

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self):
        pass

    def get_db(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        db: Session = next(self.get_db())
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                # Mavjud foydalanuvchini yangilash
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.last_seen = datetime.utcnow()
                action_text = "yangilandi"
            else:
                # Yangi foydalanuvchi qo'shish
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                db.add(user)
                action_text = "qo'shildi"

            db.commit()
            logger.info(f"Foydalanuvchi {action_text}: {user_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Foydalanuvchi qo'shishda xatolik: {e}")
            return False

    def get_user(self, user_id: int):
        db: Session = next(self.get_db())
        try:
            return db.query(User).filter(User.user_id == user_id).first()
        except Exception as e:
            logger.error(f"Foydalanuvchi olishda xatolik: {e}")
            return None

    def increment_movie_watch(self, user_id: int):
        db: Session = next(self.get_db())
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                user.movies_watched = (user.movies_watched or 0) + 1
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Film ko'rishni yangilashda xatolik: {e}")

    def is_banned(self, user_id: int):
        user = self.get_user(user_id)
        return user.is_banned if user else False

    def get_all_user_ids(self):
        db: Session = next(self.get_db())
        try:
            # Faqat ID larni olamiz, bu tezroq
            user_ids = db.query(User.user_id).filter(User.is_banned == False).all()
            return [uid for (uid,) in user_ids] # [(123,), (456,)] -> [123, 456]
        except Exception as e:
            logger.error(f"Barcha foydalanuvchi ID larini olishda xatolik: {e}")
            return []

    def get_user_stats(self):
        db: Session = next(self.get_db())
        try:
            total_users = db.query(func.count(User.user_id)).scalar()
            active_users = db.query(func.count(User.user_id)).filter(User.is_banned == False).scalar()
            return {
                "total_users": total_users,
                "active_users": active_users,
            }
        except Exception as e:
            logger.error(f"User statistikasida xatolik: {e}")
            return {"total_users": 0, "active_users": 0}

    def find_user(self, query: str):
        db: Session = next(self.get_db())
        try:
            query_str = str(query).lower().replace('@', '')
            if query_str.isdigit():
                user = db.query(User).filter(User.user_id == int(query_str)).first()
                if user:
                    return user

            user_by_username = db.query(User).filter(func.lower(User.username) == query_str).first()
            return user_by_username
        except Exception as e:
            logger.error(f"Foydalanuvchini topishda xatolik: {e}")
            return None
