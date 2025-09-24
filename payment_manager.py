# payment_manager.py
import json
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import Payment, PremiumUser, Settings, User, SessionLocal
from config import DEFAULT_PREMIUM_PRICES, PAYMENT_CARD_INFO

logger = logging.getLogger(__name__)

class PaymentManager:
    def __init__(self):
        self._init_settings()

    def get_db(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _init_settings(self):
        """Narxlar va karta ma'lumotlari uchun sozlamalarni yaratish"""
        db: Session = next(self.get_db())
        try:
            # Narxlar
            prices_setting = db.query(Settings).filter(Settings.key == "premium_prices").first()
            if not prices_setting:
                new_setting = Settings(key="premium_prices", value=json.dumps(DEFAULT_PREMIUM_PRICES))
                db.add(new_setting)
                logger.info("premium_prices sozlamasi yaratildi.")

            # Karta ma'lumotlari
            card_setting = db.query(Settings).filter(Settings.key == "payment_card_info").first()
            if not card_setting:
                new_setting = Settings(key="payment_card_info", value=json.dumps(PAYMENT_CARD_INFO))
                db.add(new_setting)
                logger.info("payment_card_info sozlamasi yaratildi.")

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Boshlang'ich to'lov sozlamalarini yaratishda xatolik: {e}")

    def get_prices(self):
        db: Session = next(self.get_db())
        try:
            setting = db.query(Settings).filter(Settings.key == "premium_prices").first()
            return json.loads(setting.value) if setting else DEFAULT_PREMIUM_PRICES
        except Exception:
            return DEFAULT_PREMIUM_PRICES

    def update_prices(self, new_prices: dict):
        db: Session = next(self.get_db())
        try:
            setting = db.query(Settings).filter(Settings.key == "premium_prices").first()
            if setting:
                setting.value = json.dumps(new_prices)
                db.commit()
                logger.info(f"Narxlar yangilandi: {new_prices}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Narxlarni yangilashda xatolik: {e}")
            return False

    def get_card_info(self):
        db: Session = next(self.get_db())
        try:
            setting = db.query(Settings).filter(Settings.key == "payment_card_info").first()
            return json.loads(setting.value) if setting else PAYMENT_CARD_INFO
        except Exception:
            return PAYMENT_CARD_INFO

    def update_card_info(self, new_card_info: dict):
        db: Session = next(self.get_db())
        try:
            setting = db.query(Settings).filter(Settings.key == "payment_card_info").first()
            if setting:
                setting.value = json.dumps(new_card_info)
                db.commit()
                logger.info("Karta ma'lumotlari yangilandi.")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Karta ma'lumotlarini yangilashda xatolik: {e}")
            return False

    def create_payment_request(self, user_id: int, plan_type: str, amount: int, check_message_link: str):
        db: Session = next(self.get_db())
        try:
            new_payment = Payment(
                id=int(time.time() * 1000), # Unikal ID
                user_id=user_id,
                plan_type=plan_type,
                amount=amount,
                check_message_link=check_message_link
            )
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)
            logger.info(f"To'lov so'rovi yaratildi: ID {new_payment.id}, User {user_id}")
            return new_payment.id
        except Exception as e:
            db.rollback()
            logger.error(f"To'lov so'rovi yaratishda xatolik: {e}")
            return None

    def get_pending_payments(self):
        db: Session = next(self.get_db())
        try:
            return db.query(Payment).filter(Payment.status == "pending").all()
        except Exception as e:
            logger.error(f"Kutilayotgan to'lovlarni olishda xatolik: {e}")
            return []

    def approve_payment(self, payment_id: int):
        db: Session = next(self.get_db())
        try:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment or payment.status != "pending":
                return False, "To'lov topilmadi yoki allaqachon ko'rib chiqilgan."

            payment.status = "approved"
            payment.processed_at = datetime.utcnow()

            # Premium obunani faollashtirish
            days = 0
            if payment.plan_type == "week": days = 7
            elif payment.plan_type == "month": days = 30
            elif payment.plan_type == "year": days = 365

            if days == 0:
                return False, "Noto'g'ri obuna turi."

            expire_date = datetime.utcnow() + timedelta(days=days)

            premium_user = db.query(PremiumUser).filter(PremiumUser.user_id == payment.user_id).first()
            if premium_user:
                premium_user.plan_type = payment.plan_type
                premium_user.start_date = datetime.utcnow()
                premium_user.expire_date = expire_date
                premium_user.payment_id = payment.id
                premium_user.is_active = True
            else:
                new_premium = PremiumUser(
                    user_id=payment.user_id,
                    plan_type=payment.plan_type,
                    start_date=datetime.utcnow(),
                    expire_date=expire_date,
                    payment_id=payment.id,
                    is_active=True
                )
                db.add(new_premium)

            db.commit()
            logger.info(f"To'lov tasdiqlandi: ID {payment.id}, User {payment.user_id}")
            return True, "Muvaffaqiyatli tasdiqlandi."
        except Exception as e:
            db.rollback()
            logger.error(f"To'lovni tasdiqlashda xatolik: {e}")
            return False, str(e)

    def reject_payment(self, payment_id: int):
        db: Session = next(self.get_db())
        try:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment or payment.status != "pending":
                return False, "To'lov topilmadi yoki allaqachon ko'rib chiqilgan."

            payment.status = "rejected"
            payment.processed_at = datetime.utcnow()
            db.commit()
            logger.info(f"To'lov rad etildi: ID {payment_id}")
            return True, "To'lov rad etildi."
        except Exception as e:
            db.rollback()
            logger.error(f"To'lovni rad etishda xatolik: {e}")
            return False, str(e)

    def is_premium_user(self, user_id: int):
        db: Session = next(self.get_db())
        try:
            premium_info = db.query(PremiumUser).filter(PremiumUser.user_id == user_id).first()
            if not premium_info or not premium_info.is_active:
                return False

            if datetime.utcnow() > premium_info.expire_date:
                premium_info.is_active = False
                db.commit()
                return False

            return True
        except Exception as e:
            # Xatolik yuz bersa, premium emas deb hisoblaymiz
            logger.error(f"Premium tekshirishda xatolik (user_id: {user_id}): {e}")
            return False

    def get_premium_info(self, user_id: int):
        db: Session = next(self.get_db())
        try:
            return db.query(PremiumUser).filter(PremiumUser.user_id == user_id).first()
        except Exception as e:
            logger.error(f"Premium ma'lumot olishda xatolik: {e}")
            return None

    def get_payment_stats(self):
        db: Session = next(self.get_db())
        try:
            total_payments = db.query(func.count(Payment.id)).scalar()
            pending_payments = db.query(func.count(Payment.id)).filter(Payment.status == 'pending').scalar()
            total_earned = db.query(func.sum(Payment.amount)).filter(Payment.status == 'approved').scalar() or 0

            # muddati tugamagan aktiv premiumlar
            active_premium_users = db.query(func.count(PremiumUser.user_id)).filter(
                PremiumUser.is_active == True,
                PremiumUser.expire_date > datetime.utcnow()
            ).scalar()

            return {
                "total_payments": total_payments,
                "pending_payments": pending_payments,
                "total_earned": total_earned,
                "active_premium_users": active_premium_users
            }
        except Exception as e:
            logger.error(f"To'lov statistikasida xatolik: {e}")
            return {}
