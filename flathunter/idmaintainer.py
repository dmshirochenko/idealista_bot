"""Supabase implementation of IDMaintainer interface"""
import threading
import sqlite3 as lite
import datetime
import json
import logging

from flathunter.abstract_processor import Processor
from flathunter.supabase_client import SupabaseClient


class SaveAllExposesProcessor(Processor):
    """Processor that saves all exposes to the database"""

    def __init__(self, config, id_watch):
        self.config = config
        self.id_watch = id_watch

    def process_expose(self, expose):
        """Save a single expose"""
        self.id_watch.save_expose(expose)
        return expose


class AlreadySeenFilter:
    """Filter exposes that have already been processed"""

    def __init__(self, id_watch):
        self.id_watch = id_watch

    def is_interesting(self, expose):
        """Returns true if an expose should be kept in the pipeline"""
        return not self.id_watch.is_processed(expose["id"], expose["crawler"])


class IdMaintainer:
    """Supabase back-end for the database"""

    __log__ = logging.getLogger("flathunt")

    def __init__(self, supabase_client: SupabaseClient, user_id: str, filter_id: str):
        self.supabase = supabase_client
        self.user_id = user_id
        self.filter_id = filter_id
        self.processed_ids = self._fetch_processed_ids()

    def _fetch_processed_ids(self):
        """
        Fetches all previously processed property IDs and their crawlers for the current user and filter,
        and stores them in a set of tuples for fast in-memory lookups.
        """
        self.__log__.debug(f"Fetching processed IDs for user {self.user_id} and filter {self.filter_id}")
        try:
            # We select both property_id and crawler to create a unique tuple.
            query = f"SELECT property_id, crawler FROM listings WHERE user_id = '{self.user_id}' AND filter_id = '{self.filter_id}' AND processed = true"
            result = self.supabase.execute_select(query)
            return {(item['property_id'], item['crawler']) for item in result}
        except Exception as e:
            self.__log__.error(f"Error fetching processed IDs: {e}")
            # It's safer to not proceed than to risk sending many duplicate notifications.
            # Raise an exception to stop the processing for this filter.
            raise Exception(f"Could not fetch processed IDs for user {self.user_id}. Aborting to prevent duplicates.") from e

    @property
    def already_seen_filter(self):
        """Returns a filter object that can be used with filter()"""
        return AlreadySeenFilter(self)

    def is_processed(self, expose_id: int, crawler: str):
        """
        Checks if an expose (as a tuple of ID and crawler) is in the set of processed IDs.
        This avoids a database query for each check.
        """
        is_processed = (int(expose_id), crawler) in self.processed_ids
        if is_processed:
            self.__log__.debug("Expose %d from %s already processed for user %s", expose_id, crawler, self.user_id)
        return is_processed

    def mark_processed(self, expose_id: int, crawler: str):
        """Mark an expose as processed in the database and update the in-memory set."""
        self.__log__.debug("mark_processed(%d, %s) for user %s", expose_id, crawler, self.user_id)
        try:
            # This should be an upsert. If the row exists, update `processed`, otherwise do nothing.
            # The `save_expose` should have already inserted the row with `processed=false`.
            # So this should be an update.
            query = f"UPDATE listings SET processed = true, updated_at = now() WHERE property_id = {expose_id} AND crawler = '{crawler}' AND user_id = '{self.user_id}' AND filter_id = '{self.filter_id}'"
            self.supabase.execute_commit(query)
            # Add the tuple to the cache to prevent it from being processed again in the same run
            self.processed_ids.add((int(expose_id), crawler))
        except Exception as e:
            self.__log__.error(f"Error marking expose {expose_id} as processed for user {self.user_id}: {e}")

    def save_expose(self, expose):
        """Saves an expose to a database"""
        self.__log__.debug("save_expose for user %s: %s", self.user_id, expose["id"])
        try:
            expose_id = int(expose["id"])
            crawler = expose["crawler"]
            details = json.dumps(expose).replace("'", "''")  # Basic SQL injection prevention for JSON

            # Upsert: Insert if not exists, do nothing if it exists.
            # The combination of (property_id, crawler, user_id, filter_id) is unique.
            query = (
                f"INSERT INTO listings (property_id, user_id, filter_id, crawler, details, processed) "
                f"VALUES ({expose_id}, '{self.user_id}', '{self.filter_id}', '{crawler}', '{details}', false) "
                f"ON CONFLICT (property_id, crawler, user_id, filter_id) DO NOTHING"
            )
            self.supabase.execute_commit(query)
        except Exception as e:
            self.__log__.error(f"Error saving expose {expose.get('id')} for user {self.user_id}: {e}")
