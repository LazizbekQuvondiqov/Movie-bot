# broadcast_manager.py
import json
import os
import logging
import time
from datetime import datetime
from threading import Lock, Thread
from config import BROADCAST_HISTORY_FILE, DATA_DIR

logger = logging.getLogger(__name__)

class BroadcastManager:
    def __init__(self):
        self.broadcast_file = BROADCAST_HISTORY_FILE
        self.lock = Lock()
        self.active_broadcasts = {}
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(self.broadcast_file):
                initial_data = {"broadcasts": {}}
                with open(self.broadcast_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Broadcast fayl yaratildi: {self.broadcast_file}")
        except Exception as e:
            logger.error(f"Broadcast fayl yaratishda xatolik: {e}")

    def _load_data(self):
        try:
            with open(self.broadcast_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.setdefault("broadcasts", {})
                return data
        except Exception as e:
            logger.error(f"Broadcast ma'lumot yuklashda xatolik: {e}")
            return {"broadcasts": {}}

    def _save_data(self, data):
        with self.lock:
            try:
                temp_file = f"{self.broadcast_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.broadcast_file)
                return True
            except Exception as e:
                logger.error(f"Broadcast ma'lumot saqlashda xatolik: {e}")
                return False

    def start_broadcast(self, bot, user_list, content_type, content, admin_id, admin_username):
        """Ommaviy xabar yuborishni boshlash"""
        try:
            broadcast_id = int(time.time() * 1000)

            broadcast_data = {
                "id": broadcast_id,
                "admin_id": admin_id,
                "admin_username": admin_username,
                "content_type": content_type,  # text, photo, video, document
                "start_time": datetime.now().isoformat(),
                "total_users": len(user_list),
                "success_count": 0,
                "failed_count": 0,
                "status": "running",  # running, completed, cancelled
                "content_preview": content.get('text', '')[:100] if content_type == 'text' else f"{content_type} content"
            }

            # Fayl ma'lumotlarga saqlash
            data = self._load_data()
            data["broadcasts"][str(broadcast_id)] = broadcast_data
            self._save_data(data)

            # Aktiv broadcast ro'yxatiga qo'shish
            self.active_broadcasts[broadcast_id] = {
                "data": broadcast_data,
                "cancelled": False
            }

            # Xabar yuborish thread ini boshlash
            thread = Thread(
                target=self._send_broadcast_messages,
                args=(bot, broadcast_id, user_list, content_type, content)
            )
            thread.daemon = True
            thread.start()

            logger.info(f"Broadcast boshlandi: ID {broadcast_id}, {len(user_list)} foydalanuvchi")
            return broadcast_id

        except Exception as e:
            logger.error(f"Broadcast boshlatishda xatolik: {e}")
            return None

    def _send_broadcast_messages(self, bot, broadcast_id, user_list, content_type, content):
        """Xabarlarni yuborish (background task)"""
        try:
            success_count = 0
            failed_count = 0

            for user_id in user_list:
                # Bekor qilinganligini tekshirish
                if broadcast_id in self.active_broadcasts and self.active_broadcasts[broadcast_id]["cancelled"]:
                    logger.info(f"Broadcast bekor qilindi: {broadcast_id}")
                    break

                try:
                    # Xabar turini aniqlash va yuborish
                    if content_type == "text":
                        bot.send_message(
                            user_id,
                            content['text'],
                            parse_mode=content.get('parse_mode', 'HTML'),
                            reply_markup=content.get('reply_markup')
                        )
                    elif content_type == "photo":
                        bot.send_photo(
                            user_id,
                            content['photo'],
                            caption=content.get('caption', ''),
                            parse_mode=content.get('parse_mode', 'HTML'),
                            reply_markup=content.get('reply_markup')
                        )
                    elif content_type == "video":
                        bot.send_video(
                            user_id,
                            content['video'],
                            caption=content.get('caption', ''),
                            parse_mode=content.get('parse_mode', 'HTML'),
                            reply_markup=content.get('reply_markup')
                        )
                    elif content_type == "document":
                        bot.send_document(
                            user_id,
                            content['document'],
                            caption=content.get('caption', ''),
                            parse_mode=content.get('parse_mode', 'HTML'),
                            reply_markup=content.get('reply_markup')
                        )

                    success_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.debug(f"Foydalanuvchiga xabar yuborishda xatolik {user_id}: {e}")

                # Rate limiting uchun kichik pauza
                time.sleep(0.05)  # 50ms

                # Har 100 ta xabardan keyin progress yangilash
                if (success_count + failed_count) % 100 == 0:
                    self._update_broadcast_progress(broadcast_id, success_count, failed_count)

            # Yakuniy natijani saqlash
            self._complete_broadcast(broadcast_id, success_count, failed_count)

        except Exception as e:
            logger.error(f"Broadcast yuborishda jiddiy xatolik: {e}")
            self._complete_broadcast(broadcast_id, success_count, failed_count, error=str(e))

    def _update_broadcast_progress(self, broadcast_id, success_count, failed_count):
        """Broadcast progressini yangilash"""
        try:
            data = self._load_data()
            broadcast_id_str = str(broadcast_id)

            if broadcast_id_str in data["broadcasts"]:
                data["broadcasts"][broadcast_id_str]["success_count"] = success_count
                data["broadcasts"][broadcast_id_str]["failed_count"] = failed_count
                self._save_data(data)

        except Exception as e:
            logger.error(f"Progress yangilashda xatolik: {e}")

    def _complete_broadcast(self, broadcast_id, success_count, failed_count, error=None):
        """Broadcastni yakunlash"""
        try:
            data = self._load_data()
            broadcast_id_str = str(broadcast_id)

            if broadcast_id_str in data["broadcasts"]:
                data["broadcasts"][broadcast_id_str]["success_count"] = success_count
                data["broadcasts"][broadcast_id_str]["failed_count"] = failed_count
                data["broadcasts"][broadcast_id_str]["end_time"] = datetime.now().isoformat()
                data["broadcasts"][broadcast_id_str]["status"] = "completed"

                if error:
                    data["broadcasts"][broadcast_id_str]["error"] = error

                self._save_data(data)

            # Aktiv ro'yxatdan o'chirish
            if broadcast_id in self.active_broadcasts:
                del self.active_broadcasts[broadcast_id]

            logger.info(f"Broadcast yakunlandi: ID {broadcast_id}, Muvaffaqiyat: {success_count}, Xatolik: {failed_count}")

        except Exception as e:
            logger.error(f"Broadcast yakunlashda xatolik: {e}")

    def cancel_broadcast(self, broadcast_id):
        """Broadcastni bekor qilish"""
        try:
            if broadcast_id in self.active_broadcasts:
                self.active_broadcasts[broadcast_id]["cancelled"] = True

                # Ma'lumotlar bazasida ham yangilash
                data = self._load_data()
                broadcast_id_str = str(broadcast_id)

                if broadcast_id_str in data["broadcasts"]:
                    data["broadcasts"][broadcast_id_str]["status"] = "cancelled"
                    data["broadcasts"][broadcast_id_str]["end_time"] = datetime.now().isoformat()
                    self._save_data(data)

                logger.info(f"Broadcast bekor qilindi: {broadcast_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Broadcast bekor qilishda xatolik: {e}")
            return False

    def get_broadcast_status(self, broadcast_id):
        """Broadcast holatini olish"""
        try:
            data = self._load_data()
            return data["broadcasts"].get(str(broadcast_id))
        except Exception as e:
            logger.error(f"Broadcast holatini olishda xatolik: {e}")
            return None

    def get_active_broadcasts(self):
        """Aktiv broadcastlar ro'yxati"""
        try:
            active_list = []
            for broadcast_id, broadcast_info in self.active_broadcasts.items():
                if not broadcast_info["cancelled"]:
                    active_list.append({
                        "id": broadcast_id,
                        "data": broadcast_info["data"]
                    })
            return active_list
        except Exception as e:
            logger.error(f"Aktiv broadcastlarni olishda xatolik: {e}")
            return []

    def get_broadcast_history(self, limit=10):
        """Broadcast tarixini olish"""
        try:
            data = self._load_data()
            broadcasts = data.get("broadcasts", {})

            # Vaqt bo'yicha saralash
            sorted_broadcasts = sorted(
                broadcasts.items(),
                key=lambda x: x[1].get('start_time', ''),
                reverse=True
            )

            return dict(sorted_broadcasts[:limit])

        except Exception as e:
            logger.error(f"Broadcast tarixini olishda xatolik: {e}")
            return {}

    def get_broadcast_stats(self):
        """Broadcast statistikasi"""
        try:
            data = self._load_data()
            broadcasts = data.get("broadcasts", {})

            total_broadcasts = len(broadcasts)
            total_sent = sum(b.get("success_count", 0) for b in broadcasts.values())
            total_failed = sum(b.get("failed_count", 0) for b in broadcasts.values())

            active_count = len(self.get_active_broadcasts())

            return {
                "total_broadcasts": total_broadcasts,
                "total_messages_sent": total_sent,
                "total_failed": total_failed,
                "active_broadcasts": active_count
            }

        except Exception as e:
            logger.error(f"Broadcast statistikasida xatolik: {e}")
            return {}
