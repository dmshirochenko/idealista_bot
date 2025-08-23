#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple user management for multi-user flat hunting
"""

import logging
from typing import Dict, Any
from flathunter.supabase_client import SupabaseClient

__log__ = logging.getLogger(__name__)


class UserManager:
    """Simple user manager that pulls paid users from filter_settings table"""

    def __init__(self, base_config):
        """
        Initialize UserManager

        Args:
            base_config: Base configuration object
        """
        self.base_config = base_config
        self.supabase_client = SupabaseClient(base_config)

    def get_active_filters(self) -> Dict[str, Dict[str, Any]]:
        """
        Get active filters that are paid and have a filter_url.

        Returns:
            Dictionary with filter_id as key and filter data as value.
        """
        try:
            filters = {"is_paid": True}
            filter_settings = self.supabase_client.read_table("filter_settings", filters=filters)

            filters_dict = {}
            for setting in filter_settings:
                filter_id = setting.get("id")
                user_id = setting.get("user_id")
                receiver_ids = setting.get("receiver_ids")
                filter_url = setting.get("filter_url")

                # We need a filter_id, user_id, receiver_ids and a URL to work with.
                if filter_id and user_id and receiver_ids and filter_url:
                    filters_dict[filter_id] = {
                        "filter_id": filter_id,
                        "user_id": user_id,
                        "filter_url": filter_url,
                        "receiver_ids": receiver_ids,
                        "is_paid": setting.get("is_paid", False),
                        "scraping_interval": setting.get("scraping_interval", 30),
                    }

            __log__.info(f"Retrieved {len(filters_dict)} active filters from database")
            return filters_dict

        except Exception as e:
            __log__.error(f"Error fetching active filters: {e}")
            return {}

    def close(self):
        """Close database connections"""
        if self.supabase_client:
            self.supabase_client.close()
