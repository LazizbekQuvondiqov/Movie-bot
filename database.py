# database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, BigInteger, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# DATABASE_URL Railway muhit o'zgaruvchilaridan olinadi
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL muhit o'zgaruvchisi topilmadi!")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Jadvallar (Modellar) ---

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    joined_date = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_banned = Column(Boolean, default=False)
    movies_watched = Column(Integer, default=0)

class Movie(Base):
    __tablename__ = "movies"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    original_title = Column(String, nullable=True)
    year = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    poster_url = Column(String, nullable=True)
    genres = Column(Text, nullable=True) # Janrlarni vergul bilan ajratilgan matn sifatida saqlaymiz
    countries = Column(Text, nullable=True)
    views = Column(Integer, default=0)
    added_date = Column(DateTime, default=datetime.utcnow)
    tmdb_id = Column(Integer, nullable=True)

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    url = Column(String, nullable=False)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    added_date = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    plan_type = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="pending") # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    check_message_link = Column(String, nullable=True) # Chek yuborilgan xabar linki

class PremiumUser(Base):
    __tablename__ = "premium_users"
    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    plan_type = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    expire_date = Column(DateTime, nullable=False)
    payment_id = Column(BigInteger, ForeignKey('payments.id'))
    is_active = Column(Boolean, default=True)

class Broadcast(Base):
    __tablename__ = "broadcasts"
    id = Column(BigInteger, primary_key=True, index=True)
    admin_id = Column(BigInteger)
    content_type = Column(String)
    content_preview = Column(Text)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="running") # running, completed, cancelled
    total_users = Column(Integer)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)

# Sozlamalar uchun alohida jadval
class Settings(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text) # Narxlar, karta ma'lumotlari JSON matn sifatida saqlanadi

def init_db():
    """Ma'lumotlar bazasi jadvallarini yaratish"""
    Base.metadata.create_all(bind=engine)
    print("Ma'lumotlar bazasi jadvallari yaratildi yoki mavjud.")
class Favorite(Base):
    __tablename__ = "favorites"
    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    movie_id = Column(Integer, ForeignKey('movies.id'), primary_key=True)
    added_date = Column(DateTime, default=datetime.utcnow)
