"""Functions and classes related to sending Telegram messages"""
import urllib.request
import urllib.parse
import urllib.error
import logging
import requests

from flathunter.abstract_processor import Processor


class SenderTelegram(Processor):
    """Expose processor that sends Telegram messages"""

    __log__ = logging.getLogger("flathunt")

    def __init__(self, config, receivers=None, admin_config=False):
        self.config = config
        if admin_config:
            admin_conf = self.config.get("telegram_admin", dict())
            self.bot_token = admin_conf.get("bot_token_admin")
            receiver_id = admin_conf.get("receiver_id_admin")
            self.receiver_ids = [receiver_id] if receiver_id else []
            self.admin_config = True
        else:
            self.bot_token = self.config.get("telegram", dict()).get("bot_token", "")
            if receivers is None:
                self.receiver_ids = self.config.get("telegram", dict()).get(
                    "receiver_ids", list()
                )
            else:
                self.receiver_ids = receivers
            self.admin_config = False

    def process_expose(self, expose):
        """Send a message to a user describing the expose"""
        message = (
            self.config.get("message", "")
            .format(
                title=expose["title"],
                rooms=expose["rooms"],
                size=expose["size"],
                price=expose["price"],
                url=expose["url"],
                address=expose["address"],
                durations="" if "durations" not in expose else expose["durations"],
            )
            .strip()
        )
        self.send_msg(message)
        return expose

    def send_msg(self, message):
        """Send messages to each of the receivers in receiver_ids, with an inline 'Ask AI' button"""
        if self.receiver_ids is None:
            return

        for chat_id in self.receiver_ids:
            if not chat_id:
                continue
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",  # optional; use only if your message uses formatting
            }
            if not self.admin_config:
                payload["reply_markup"] = {
                    "inline_keyboard": [[{"text": "Ask AI", "callback_data": "ask_ai"}]]
                }

            self.__log__.debug("Sending payload: %s", payload)
            resp = requests.post(url, json=payload)
            self.__log__.debug("Got response (%i): %s", resp.status_code, resp.content)

            data = resp.json()

            if resp.status_code != 200:
                self.__log__.error(
                    "When sending bot message, we got status %i with message: %s", resp.status_code, data
                )
