# payment_manager.py
import json
import os
import logging
import time
from datetime import datetime, timedelta
from threading import Lock
from config import PREMIUM_PLANS_FILE, DATA_DIR, DEFAULT_PREMIUM_PRICES, PAYMENT_CARD_INFO

logger = logging.getLogger(__name__)

class PaymentManager:
    def __init__(self):
        self.premium_file = PREMIUM_PLANS_FILE
        self.lock = Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(self.premium_file):
                initial_data = {
                    "payments": {},
                    "premium_users": {},
                    "prices": DEFAULT_PREMIUM_PRICES,
                    "card_info": PAYMENT_CARD_INFO
                }
                with open(self.premium_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Premium fayl yaratildi: {self.premium_file}")
        except Exception as e:
            logger.error(f"Premium fayl yaratishda xatolik: {e}")

    def _load_data(self):
        try:
            with open(self.premium_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Standart struktura
                data.setdefault("payments", {})
                data.setdefault("premium_users", {})
                data.setdefault("prices", DEFAULT_PREMIUM_PRICES)
                data.setdefault("card_info", PAYMENT_CARD_INFO)
                return data
        except Exception as e:
            logger.error(f"Premium ma'lumot yuklashda xatolik: {e}")
            return {
                "payments": {},
                "premium_users": {},
                "prices": DEFAULT_PREMIUM_PRICES,
                "card_info": PAYMENT_CARD_INFO
            }

    def _save_data(self, data):
        with self.lock:
            try:
                temp_file = f"{self.premium_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.premium_file)
                return True
            except Exception as e:
                logger.error(f"Premium ma'lumot saqlashda xatolik: {e}")
                return False

    def get_prices(self):
        """Joriy narxlarni olish"""
        data = self._load_data()
        return data.get("prices", DEFAULT_PREMIUM_PRICES)

    def update_prices(self, new_prices):
        """Narxlarni yangilash"""
        try:
            data = self._load_data()
            data["prices"] = new_prices
            if self._save_data(data):
                logger.info(f"Narxlar yangilandi: {new_prices}")
                return True
            return False
        except Exception as e:
            logger.error(f"Narx yangilashda xatolik: {e}")
            return False

    def get_card_info(self):
        """Karta ma'lumotlarini olish"""
        data = self._load_data()
        return data.get("card_info", PAYMENT_CARD_INFO)

    def update_card_info(self, new_card_info):
        """Karta ma'lumotlarini yangilash"""
        try:
            data = self._load_data()
            data["card_info"] = new_card_info
            if self._save_data(data):
                logger.info("Karta ma'lumotlari yangilandi")
                return True
            return False
        except Exception as e:
            logger.error(f"Karta ma'lumot yangilashda xatolik: {e}")
            return False

    def create_payment_request(self, user_id, username, plan_type, amount, file_id=None):
        """To'lov so'rovi yaratish"""
        try:
            data = self._load_data()
            payment_id = int(time.time() * 1000)  # Unique ID

            payment_data = {
                "user_id": user_id,
                "username": username or "Noma'lum",
                "plan_type": plan_type,
                "amount": amount,
                "file_id": file_id,  # Screenshot file_id
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "processed_at": None,
                "admin_note": None
            }

            data["payments"][str(payment_id)] = payment_data

            if self._save_data(data):
                logger.info(f"To'lov so'rovi yaratildi: ID {payment_id}, User {user_id}")
                return payment_id
            return None
        except Exception as e:
            logger.error(f"To'lov so'rovi yaratishda xatolik: {e}")
            return None

    def get_pending_payments(self):
        """Kutilayotgan to'lovlarni olish"""
        try:
            data = self._load_data()
            pending = {}
            for payment_id, payment_data in data["payments"].items():
                if payment_data["status"] == "pending":
                    pending[payment_id] = payment_data
            return pending
        except Exception as e:
            logger.error(f"Kutilayotgan to'lovlarni olishda xatolik: {e}")
            return {}

    def approve_payment(self, payment_id, admin_id, admin_note=""):
        """To'lovni tasdiqlash va Premium faollashtirish"""
        try:
            data = self._load_data()
            payment_id_str = str(payment_id)

            if payment_id_str not in data["payments"]:
                return False, "To'lov so'rovi topilmadi"

            payment = data["payments"][payment_id_str]
            if payment["status"] != "pending":
                return False, "To'lov allaqachon ko'rib chiqilgan"

            # To'lovni tasdiqlash
            payment["status"] = "approved"
            payment["processed_at"] = datetime.now().isoformat()
            payment["admin_note"] = admin_note
            payment["processed_by"] = admin_id

            # Premium obunani faollashtirish
            user_id = payment["user_id"]
            plan_type = payment["plan_type"]

            # Muddat hisoblash
            if plan_type == "week":
                expire_date = datetime.now() + timedelta(days=7)
            elif plan_type == "month":
                expire_date = datetime.now() + timedelta(days=30)
            elif plan_type == "year":
                expire_date = datetime.now() + timedelta(days=365)
            else:
                return False, "Noto'g'ri obuna turi"

            # Premium foydalanuvchi qo'shish
            data["premium_users"][str(user_id)] = {
                "plan_type": plan_type,
                "start_date": datetime.now().isoformat(),
                "expire_date": expire_date.isoformat(),
                "payment_id": payment_id,
                "is_active": True
            }

            if self._save_data(data):
                logger.info(f"To'lov tasdiqlandi va Premium faollashtirildi: Payment ID {payment_id}, User {user_id}")
                return True, "Muvaffaqiyatli tasdiqlandi"

            return False, "Ma'lumotlarni saqlashda xatolik"

        except Exception as e:
            logger.error(f"To'lovni tasdiqd xatolik: {e}")
            return False, str(e)

    def reject_payment(self, payment_id, admin_id, admin_note=""):
        """To'lovni rad etish"""
        try:
            data = self._load_data()
            payment_id_str = str(payment_id)

            if payment_id_str not in data["payments"]:
                return False, "To'lov so'rovi topilmadi"

            payment = data["payments"][payment_id_str]
            if payment["status"] != "pending":
                return False, "To'lov allaqachon ko'rib chiqilgan"

            # To'lovni rad etish
            payment["status"] = "rejected"
            payment["processed_at"] = datetime.now().isoformat()
            payment["admin_note"] = admin_note
            payment["processed_by"] = admin_id

            if self._save_data(data):
                logger.info(f"To'lov rad etildi: Payment ID {payment_id}")
                return True, "To'lov rad etildi"

            return False, "Ma'lumotlarni saqlashda xatolik"

        except Exception as e:
            logger.error(f"To'lovni rad etishda xatolik: {e}")
            return False, str(e)

    def is_premium_user(self, user_id):
        """Foydalanuvchi Premium ekanligini tekshirish"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)

            if user_id_str not in data["premium_users"]:
                return False

            user_premium = data["premium_users"][user_id_str]
            if not user_premium.get("is_active", False):
                return False

            # Muddat tugaganligini tekshirish
            expire_date = datetime.fromisoformat(user_premium["expire_date"])
            if datetime.now() > expire_date:
                # Premium muddati tugagan
                user_premium["is_active"] = False
                self._save_data(data)
                return False

            return True

        except Exception as e:
            logger.error(f"Premium tekshirishda xatolik: {e}")
            return False

    def get_premium_info(self, user_id):
        """Premium ma'lumotlarini olish"""
        try:
            data = self._load_data()
            user_id_str = str(user_id)

            if user_id_str in data["premium_users"]:
                return data["premium_users"][user_id_str]
            return None

        except Exception as e:
            logger.error(f"Premium ma'lumot olishda xatolik: {e}")
            return None

    def get_payment_stats(self):
        """To'lov statistikasi"""
        try:
            data = self._load_data()
            payments = data.get("payments", {})

            total_payments = len(payments)
            approved_count = sum(1 for p in payments.values() if p["status"] == "approved")
            pending_count = sum(1 for p in payments.values() if p["status"] == "pending")
            rejected_count = sum(1 for p in payments.values() if p["status"] == "rejected")

            total_earned = sum(p["amount"] for p in payments.values() if p["status"] == "approved")
            active_premium = sum(1 for p in data.get("premium_users", {}).values() if p.get("is_active", False))

            return {
                "total_payments": total_payments,
                "approved_payments": approved_count,
                "pending_payments": pending_count,
                "rejected_payments": rejected_count,
                "total_earned": total_earned,
                "active_premium_users": active_premium
            }

        except Exception as e:
            logger.error(f"To'lov statistikasida xatolik: {e}")
            return {}
