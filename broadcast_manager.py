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

    def get_db(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def start_broadcast(self, bot, user_list, content, admin_id):
        db: Session = next(self.get_db())
        try:
            broadcast_id = int(time.time() * 1000)

            # Content preview yaratish
            content_type = content.content_type
            if content_type == 'text':
                preview = content.text[:100]
            else:
                preview = f"{content_type.capitalize()} fayl"

            new_broadcast = Broadcast(
                id=broadcast_id,
                admin_id=admin_id,
                content_type=content_type,
                content_preview=preview,
                total_users=len(user_list),
                status="running"
            )
            db.add(new_broadcast)
            db.commit()

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
        except Exception as e:
            db.rollback()
            logger.error(f"Broadcast boshlatishda xatolik: {e}")
            return None

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
        db: Session = next(self.get_db())
        try:
            broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
            if broadcast:
                broadcast.success_count = success
                broadcast.failed_count = failed
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Progress yangilashda xatolik: {e}")

    def _complete_broadcast(self, broadcast_id, success, failed):
        db: Session = next(self.get_db())
        try:
            broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
            if broadcast:
                broadcast.success_count = success
                broadcast.failed_count = failed
                broadcast.end_time = datetime.utcnow()

                # Agar bekor qilingan bo'lsa, statusni o'zgartirmaymiz
                if broadcast.status == "running":
                    broadcast.status = "completed"

                db.commit()

            with self.lock:
                if broadcast_id in self.active_broadcasts:
                    del self.active_broadcasts[broadcast_id]

            logger.info(f"Broadcast yakunlandi: ID {broadcast_id}, Muvaffaqiyat: {success}, Xatolik: {failed}")
        except Exception as e:
            db.rollback()
            logger.error(f"Broadcast yakunlashda xatolik: {e}")

    def cancel_broadcast(self, broadcast_id):
        db: Session = next(self.get_db())
        try:
            with self.lock:
                if broadcast_id in self.active_broadcasts:
                    self.active_broadcasts[broadcast_id]["cancelled"] = True

            broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
            if broadcast and broadcast.status == "running":
                broadcast.status = "cancelled"
                broadcast.end_time = datetime.utcnow()
                db.commit()
                logger.info(f"Broadcast bekor qilindi: {broadcast_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Broadcast bekor qilishda xatolik: {e}")
            return False

    def get_broadcast_history(self, limit=10):
        db: Session = next(self.get_db())
        try:
            return db.query(Broadcast).order_by(desc(Broadcast.start_time)).limit(limit).all()
        except Exception as e:
            logger.error(f"Broadcast tarixini olishda xatolik: {e}")
            return []

    def get_broadcast_stats(self):
        db: Session = next(self.get_db())
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
            return {}
