# payment_manager.py (YAKUNIY VARIANT)

import json
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from database import Payment, PremiumUser, Settings, SessionLocal
from config import DEFAULT_PREMIUM_PRICES, PAYMENT_CARD_INFO

logger = logging.getLogger(__name__)

class PaymentManager:
    def __init__(self):
        self._init_settings()

    # get_db() funksiyasi olib tashlandi.

    def _init_settings(self):
        """Narxlar va karta ma'lumotlari uchun sozlamalarni yaratish (samarali usulda)"""
        with SessionLocal() as db:
            try:
                # Narxlar uchun "upsert"
                prices_stmt = insert(Settings).values(
                    key="premium_prices", value=json.dumps(DEFAULT_PREMIUM_PRICES)
                ).on_conflict_do_nothing(index_elements=['key'])
                db.execute(prices_stmt)

                # Karta ma'lumotlari uchun "upsert"
                card_stmt = insert(Settings).values(
                    key="payment_card_info", value=json.dumps(PAYMENT_CARD_INFO)
                ).on_conflict_do_nothing(index_elements=['key'])
                db.execute(card_stmt)

                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Boshlang'ich to'lov sozlamalarini yaratishda xatolik: {e}")

    def get_setting_value(self, key: str, default_value):
        """Umumiy sozlamalarni olish uchun yordamchi funksiya"""
        with SessionLocal() as db:
            try:
                value = db.query(Settings.value).filter(Settings.key == key).scalar()
                return json.loads(value) if value else default_value
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"'{key}' sozlamasini olishda xatolik: {e}")
                return default_value

    def update_setting_value(self, key: str, new_value_dict: dict):
        """Umumiy sozlamalarni yangilash uchun yordamchi funksiya"""
        with SessionLocal() as db:
            try:
                db.query(Settings).filter(Settings.key == key).update(
                    {Settings.value: json.dumps(new_value_dict)},
                    synchronize_session=False
                )
                db.commit()
                logger.info(f"'{key}' sozlamasi yangilandi.")
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"'{key}' sozlamasini yangilashda xatolik: {e}")
                return False

    def get_prices(self):
        return self.get_setting_value("premium_prices", DEFAULT_PREMIUM_PRICES)

    def update_prices(self, new_prices: dict):
        return self.update_setting_value("premium_prices", new_prices)

    def get_card_info(self):
        return self.get_setting_value("payment_card_info", PAYMENT_CARD_INFO)

    def update_card_info(self, new_card_info: dict):
        return self.update_setting_value("payment_card_info", new_card_info)

    def create_payment_request(self, user_id: int, plan_type: str, amount: int, check_message_link: str):
        with SessionLocal() as db:
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
        with SessionLocal() as db:
            try:
                return db.query(Payment).filter(Payment.status == "pending").order_by(Payment.created_at).all()
            except Exception as e:
                logger.error(f"Kutilayotgan to'lovlarni olishda xatolik: {e}")
                return []

    def approve_payment(self, payment_id: int):
        with SessionLocal() as db:
            try:
                payment = db.query(Payment).filter(Payment.id == payment_id, Payment.status == "pending").with_for_update().first()
                if not payment:
                    return False, "To'lov topilmadi yoki allaqachon ko'rib chiqilgan."

                payment.status = "approved"
                payment.processed_at = datetime.utcnow()

                days_map = {"week": 7, "month": 30, "year": 365}
                days = days_map.get(payment.plan_type)
                if not days:
                    raise ValueError("Noto'g'ri obuna turi.")

                expire_date = datetime.utcnow() + timedelta(days=days)

                # PremiumUser uchun "upsert" (INSERT ... ON CONFLICT DO UPDATE)
                stmt = insert(PremiumUser).values(
                    user_id=payment.user_id,
                    plan_type=payment.plan_type,
                    start_date=datetime.utcnow(),
                    expire_date=expire_date,
                    payment_id=payment.id,
                    is_active=True
                )
                # Agar user_id allaqachon mavjud bo'lsa, uni yangilaymiz
                update_stmt = stmt.on_conflict_do_update(
                    index_elements=['user_id'],
                    set_={
                        'plan_type': stmt.excluded.plan_type,
                        'start_date': stmt.excluded.start_date,
                        'expire_date': stmt.excluded.expire_date,
                        'payment_id': stmt.excluded.payment_id,
                        'is_active': stmt.excluded.is_active
                    }
                )
                db.execute(update_stmt)
                db.commit()

                logger.info(f"To'lov tasdiqlandi: ID {payment.id}, User {payment.user_id}")
                return True, "Muvaffaqiyatli tasdiqlandi."
            except Exception as e:
                db.rollback()
                logger.error(f"To'lovni tasdiqlashda xatolik: {e}")
                return False, str(e)

    def reject_payment(self, payment_id: int):
        with SessionLocal() as db:
            try:
                result = db.query(Payment).filter(Payment.id == payment_id, Payment.status == "pending").update({
                    Payment.status: "rejected",
                    Payment.processed_at: datetime.utcnow()
                }, synchronize_session=False)
                db.commit()

                if result > 0:
                    logger.info(f"To'lov rad etildi: ID {payment_id}")
                    return True, "To'lov rad etildi."
                else:
                    return False, "To'lov topilmadi yoki allaqachon ko'rib chiqilgan."
            except Exception as e:
                db.rollback()
                logger.error(f"To'lovni rad etishda xatolik: {e}")
                return False, str(e)

    def is_premium_user(self, user_id: int):
        with SessionLocal() as db:
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
                db.rollback()
                logger.error(f"Premium tekshirishda xatolik (user_id: {user_id}): {e}")
                return False

    def get_premium_info(self, user_id: int):
        with SessionLocal() as db:
            try:
                return db.query(PremiumUser).filter(PremiumUser.user_id == user_id).first()
            except Exception as e:
                logger.error(f"Premium ma'lumot olishda xatolik: {e}")
                return None

    def get_payment_stats(self):
        with SessionLocal() as db:
            try:
                stats_query = db.query(
                    func.count(Payment.id),
                    func.count(Payment.id).filter(Payment.status == 'pending'),
                    func.sum(Payment.amount).filter(Payment.status == 'approved')
                )
                total, pending, earned = stats_query.one()

                active_premium = db.query(func.count(PremiumUser.user_id)).filter(
                    PremiumUser.is_active == True,
                    PremiumUser.expire_date > datetime.utcnow()
                ).scalar()

                return {
                    "total_payments": total or 0,
                    "pending_payments": pending or 0,
                    "total_earned": earned or 0,
                    "active_premium_users": active_premium or 0
                }
            except Exception as e:
                logger.error(f"To'lov statistikasida xatolik: {e}")
                return {}
