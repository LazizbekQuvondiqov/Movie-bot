# broadcast_manager.py
import logging
import time
from datetime import datetime
from threading import Thread, Lock
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import Broadcast, SessionLocal

logger = logging.getLogger(__name__)

class BroadcastManager:
    def __init__(self):
        self.active_broadcasts = {} # {broadcast_id: {"cancelled": False}}
        self.lock = Lock()

    def start_broadcast(self, bot, user_list, content, admin_id):
        # Content preview yaratish. Buni baza operatsiyasidan oldin qilamiz.
        try:
            content_type = content.content_type
            if content_type == 'text':
                preview = content.text[:100]
            else:
                preview = f"{content_type.capitalize()} fayl"
        except Exception as e:
            logger.error(f"Broadcast uchun content preview yaratishda xatolik: {e}")
            # Agar content bilan muammo bo'lsa, preview'ni umumiy qilib belgilaymiz.
            preview = "Media fayl"
            content_type = content.content_type or "unknown"

        broadcast_id = int(time.time() * 1000)

        with SessionLocal() as db:
            try:
                new_broadcast = Broadcast(
                    id=broadcast_id,
                    admin_id=admin_id,
                    content_type=content_type,
                    content_preview=preview,
                    total_users=len(user_list),
                    status="running"  # Statusni "pending" yoki "starting" qilsa ham bo'ladi
                )
                db.add(new_broadcast)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Broadcast'ni bazaga saqlashda xatolik: {e}")
                return None # Agar bazaga saqlay olmasak, jarayonni boshlamaymiz.

        # Faqat bazaga muvaffaqiyatli yozilgandan keyingina jarayonni boshlaymiz
        with self.lock:
            self.active_broadcasts[broadcast_id] = {"cancelled": False}

        thread = Thread(
            target=self._send_broadcast_messages,
            args=(bot, broadcast_id, user_list, content)
        )
        thread.daemon = True
        thread.start()

        logger.info(f"Broadcast boshlandi: ID {broadcast_id}, {len(user_list)} foydalanuvchi")
        return broadcast_id
    def _send_broadcast_messages(self, bot, broadcast_id, user_list, content):
        success_count = 0
        failed_count = 0

        for user_id in user_list:
            with self.lock:
                if self.active_broadcasts.get(broadcast_id, {}).get("cancelled"):
                    logger.info(f"Broadcast bekor qilindi: {broadcast_id}")
                    break
            try:
                bot.copy_message(user_id, content.chat.id, content.message_id, reply_markup=content.reply_markup)
                success_count += 1
            except Exception as e:
                failed_count += 1
                logger.debug(f"Foydalanuvchiga ({user_id}) xabar yuborishda xatolik: {e}")

            time.sleep(0.05) # 50ms

            if (success_count + failed_count) % 100 == 0:
                self._update_broadcast_progress(broadcast_id, success_count, failed_count)

        self._complete_broadcast(broadcast_id, success_count, failed_count)

    def _update_broadcast_progress(self, broadcast_id, success, failed):
        with SessionLocal() as db:
            try:
                # Bu yerda to'liq obyektni olish o'rniga to'g'ridan-to'g'ri UPDATE so'rovini bajaramiz.
                # Bu "SELECT, keyin UPDATE" qilishdan ko'ra ancha tezroq, chunki bazaga bitta so'rov yuboriladi.
                db.query(Broadcast).filter(Broadcast.id == broadcast_id).update(
                    {
                        Broadcast.success_count: success,
                        Broadcast.failed_count: failed
                    },
                    synchronize_session=False # Muhim: sessiyani yangilashga vaqt sarflamaymiz
                )
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Progress yangilashda xatolik: {e}")
    def _complete_broadcast(self, broadcast_id, success, failed):
        with SessionLocal() as db:
            try:
                # .with_for_update() qatori jadvaldagi shu yozuvni bloklaydi,
                # bu bir vaqtning o'zida boshqa jarayon uni o'zgartirishining oldini oladi.
                broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).with_for_update().first()

                if broadcast:
                    broadcast.success_count = success
                    broadcast.failed_count = failed
                    broadcast.end_time = datetime.utcnow()

                    # Agar broadcast bekor qilinmagan bo'lsa, "completed" deb belgilaymiz.
                    # `broadcast.status` allaqachon "cancelled" bo'lishi mumkin (cancel_broadcast orqali).
                    if broadcast.status == "running":
                        broadcast.status = "completed"

                    db.commit()
                    logger.info(f"Broadcast ma'lumotlari bazada yakunlandi. ID: {broadcast_id}")
                else:
                    logger.warning(f"Yakunlash uchun broadcast topilmadi. ID: {broadcast_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Broadcast bazada yakunlashda xatolik: {e}")
                # Agar bazada xatolik bo'lsa ham, xotiradan tozalashga harakat qilamiz

        # Ma'lumotlar bazasi operatsiyasidan so'ng xotiradagi ro'yxatni tozalaymiz.
        with self.lock:
            if broadcast_id in self.active_broadcasts:
                del self.active_broadcasts[broadcast_id]
                logger.info(f"Aktiv broadcastlar ro'yxatidan o'chirildi. ID: {broadcast_id}")

        logger.info(f"Broadcast jarayoni to'liq yakunlandi: ID {broadcast_id}, Muvaffaqiyat: {success}, Xatolik: {failed}")
    def cancel_broadcast(self, broadcast_id):
        with SessionLocal() as db:
            try:
                # Birinchi navbatda xotiradagi (in-memory) holatni o'zgartiramiz.
                # Bu juda tez operatsiya, shuning uchun bazaga murojaatdan oldin qilgan ma'qul.
                with self.lock:
                    if broadcast_id in self.active_broadcasts:
                        self.active_broadcasts[broadcast_id]["cancelled"] = True

                # Endi ma'lumotlar bazasidagi yozuvni yangilaymiz.
                broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
                if broadcast and broadcast.status == "running":
                    broadcast.status = "cancelled"
                    broadcast.end_time = datetime.utcnow()
                    db.commit()
                    logger.info(f"Broadcast ma'lumotlar bazasida bekor qilindi: {broadcast_id}")
                    return True

                # Agar bazada yozuv topilmasa yoki statusi "running" bo'lmasa.
                logger.warning(f"Bekor qilish uchun broadcast topilmadi yoki allaqachon tugagan. ID: {broadcast_id}")
                return False

            except Exception as e:
                db.rollback()
                logger.error(f"Broadcast bekor qilishda xatolik: {e}")
                return False
    def get_broadcast_history(self, limit=10):
        with SessionLocal() as db:
            try:
                return db.query(Broadcast).order_by(desc(Broadcast.start_time)).limit(limit).all()
            except Exception as e:
                logger.error(f"Broadcast tarixini olishda xatolik: {e}")
                return []

    def get_broadcast_stats(self):
      with SessionLocal() as db:
          try:
              total_broadcasts = db.query(func.count(Broadcast.id)).scalar()
              total_sent = db.query(func.sum(Broadcast.success_count)).scalar() or 0

              with self.lock:
                  active_count = len(self.active_broadcasts)

              return {
                  "total_broadcasts": total_broadcasts,
                  "total_messages_sent": total_sent,
                  "active_broadcasts": active_count
              }
          except Exception as e:
              logger.error(f"Broadcast statistikasida xatolik: {e}")
              return {
                  "total_broadcasts": 0,
                  "total_messages_sent": 0,
                  "active_broadcasts": 0
              }
