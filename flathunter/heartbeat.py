"""Providing heartbeat messages"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from flathunter.config import Config
from flathunter.sender_telegram import SenderTelegram
from flathunter.supabase_client import SupabaseClient


class Heartbeat:
    """heartbeat class - Will inform the user on regular intervals whether the bot is still alive"""

    __log__ = logging.getLogger("flathunt")

    def __init__(self, config):
        self.config = config
        if not isinstance(self.config, Config):
            raise Exception("Invalid config for hunter - should be a 'Config' object")

        admin_config = self.config.get("telegram_admin")
        if admin_config:
            self.notifier = SenderTelegram(config, admin_config=True)
        else:
            self.notifier = None
        
        try:
            self.supabase_client = SupabaseClient(config)
        except Exception as e:
            self.__log__.error(f"Failed to initialize SupabaseClient in Heartbeat: {e}")
            self.supabase_client = None

    def send_heartbeat(self):
        """Send a new heartbeat message"""
        session = None
        try:
            if not self.notifier:
                return

            if not self.supabase_client or not self.supabase_client.db_url:
                self.notifier.send_msg(
                    "Beep Boop. This is a heartbeat message. Your bot is searching actively for flats. (Supabase connection failed)"
                )
                return

            # Define the time window
            ten_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=10)

            session = self.supabase_client.get_session()

            # Query for total listings
            total_listings_query = text("SELECT COUNT(*) FROM public.listings WHERE created > :created_after")
            total_listings = session.execute(total_listings_query, {'created_after': ten_minutes_ago}).scalar_one_or_none() or 0

            # Query for unique users
            unique_users_query = text("SELECT COUNT(DISTINCT user_id) FROM public.listings WHERE created > :created_after")
            unique_users = session.execute(unique_users_query, {'created_after': ten_minutes_ago}).scalar_one_or_none() or 0

            message = (
                f"Heartbeat check:\n"
                f"- Unique users with new listings in last 10 mins: {unique_users}\n"
                f"- Total new listings in last 10 mins: {total_listings}"
            )

            self.notifier.send_msg(message)

        except Exception as e:
            self.__log__.error(f"Failed to send heartbeat message: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()
