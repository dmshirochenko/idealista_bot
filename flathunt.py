#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flathunter - search for flats by crawling property portals, and receive telegram
   messages about them. This is the main command-line executable, for running on the
   console. To run as a webservice, look at main.py"""

import argparse
import os
import logging
import sys
import time
import yaml
from pprint import pformat

from flathunter.idmaintainer import IdMaintainer
from flathunter.hunter import Hunter
from flathunter.config import Config
from flathunter.heartbeat import Heartbeat
from flathunter.user_manager import UserManager


# init logging
if os.name == "posix":
    # coloring on linux
    CYELLOW = "\033[93m"
    CBLUE = "\033[94m"
    COFF = "\033[0m"
    LOG_FORMAT = (
        "["
        + CBLUE
        + "%(asctime)s"
        + COFF
        + "|"
        + CBLUE
        + "%(filename)-18s"
        + COFF
        + "|"
        + CYELLOW
        + "%(levelname)-8s"
        + COFF
        + "]: %(message)s"
    )
else:
    # else without color
    LOG_FORMAT = "[%(asctime)s|%(filename)-18s|%(levelname)-8s]: %(message)s"
logging.basicConfig(format=LOG_FORMAT, datefmt="%Y/%m/%d %H:%M:%S", level=logging.INFO)
__log__ = logging.getLogger("flathunt")


def create_user_config(base_config, user_data):
    """
    Create user-specific configuration

    Args:
        base_config: Base configuration object
        user_data: User data from database

    Returns:
        User-specific Config object
    """
    # Create a new config dict based on base config
    # Copy from base_config.config (the actual configuration dictionary)
    user_config_dict = base_config.config.copy()

    # Override with user-specific settings
    if user_data.get("filter_url"):
        user_config_dict["urls"] = [user_data["filter_url"]]

    if user_data.get("receiver_ids"):
        if "telegram" not in user_config_dict:
            user_config_dict["telegram"] = {}
        # Make sure to copy existing telegram config but override receiver_ids
        if "telegram" in base_config.config:
            user_config_dict["telegram"] = base_config.config["telegram"].copy()
        user_config_dict["telegram"]["receiver_ids"] = user_data["receiver_ids"]

    # Convert config dict to YAML string and create Config object
    config_yaml = yaml.dump(user_config_dict)
    return Config(string=config_yaml)


def launch_flat_hunt_for_user(user_config, user_id, heartbeat=None):
    """
    Launch flat hunting for a specific user

    Args:
        user_config: User-specific configuration
        user_id: User ID for logging and ID tracking
        heartbeat: Heartbeat instance
    """
    # Create user-specific ID maintainer
    id_watch = IdMaintainer(f"{user_config.database_location()}/processed_ids_user_{user_id}.db")

    hunter = Hunter(user_config, id_watch)

    __log__.info(f"Starting flat hunt for user {user_id}")

    try:
        hunter.hunt_flats()
        __log__.info(f"Completed flat hunt for user {user_id}")
    except Exception as e:
        __log__.error(f"Error hunting flats for user {user_id}: {e}")


def launch_flat_hunt_multi_user(base_config, heartbeat=None):
    """
    Launch flat hunting for multiple users sequentially

    Args:
        base_config: Base configuration
        heartbeat: Heartbeat instance
    """
    user_manager = UserManager(base_config)
    counter = 0

    try:
        __log__.info("Starting multi-user flat hunting")

        while base_config.get("loop", dict()).get("active", False):
            counter += 1

            # Send heartbeat
            if heartbeat:
                counter = heartbeat.send_heartbeat(counter)

            # Get paid users for this cycle
            try:
                users_dict = user_manager.get_paid_users()
                __log__.info(f"Found {len(users_dict)} paid users")
            except Exception as e:
                __log__.error(f"Error fetching users: {e}")
                time.sleep(base_config.get("loop", dict()).get("sleeping_time", 60 * 10))
                continue

            if not users_dict:
                __log__.warning("No paid users found, sleeping...")
                time.sleep(base_config.get("loop", dict()).get("sleeping_time", 60 * 10))
                continue

            # Process each user sequentially
            for i, (user_id, user_data) in enumerate(users_dict.items(), 1):
                try:
                    __log__.info(f"Processing user {user_id} ({i}/{len(users_dict)})")

                    # Create user-specific config
                    user_config = create_user_config(base_config, user_data)

                    # Hunt flats for this user
                    launch_flat_hunt_for_user(user_config, user_id, heartbeat)

                    # Small delay between users to avoid overwhelming servers
                    if i < len(users_dict):
                        time.sleep(5)

                except Exception as e:
                    __log__.error(f"Error processing user {user_id}: {e}")
                    continue

            # Sleep before next cycle
            sleep_time = base_config.get("loop", dict()).get("sleeping_time", 60 * 10)
            __log__.info(f"Completed cycle {counter}, sleeping for {sleep_time} seconds")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        __log__.info("Received interrupt signal, stopping...")
    except Exception as e:
        __log__.error(f"Error in multi-user flat hunting: {e}")
    finally:
        user_manager.close()


def launch_flat_hunt(config, heartbeat=None):
    """Starts the crawler / notification loop"""
    id_watch = IdMaintainer("%s/processed_ids.db" % config.database_location())

    hunter = Hunter(config, id_watch)
    hunter.hunt_flats()
    counter = 0

    __log__.debug("Launch starts from config: %s", pformat(config))

    while config.get("loop", dict()).get("active", False):
        counter += 1
        counter = heartbeat.send_heartbeat(counter)
        time.sleep(config.get("loop", dict()).get("sleeping_time", 60 * 10))
        hunter.hunt_flats()


def main():
    """Processes command-line arguments, loads the config, launches the flathunter"""
    parser = argparse.ArgumentParser(
        description="Searches for flats on property portals and sends " + "results to Telegram Users (Multi-User Mode)",
        epilog="Designed by Nody",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=argparse.FileType("r", encoding="UTF-8"),
        default="%s/config.yaml" % os.path.dirname(os.path.abspath(__file__)),
        help="Config file to use. If not set, try to use '%s/config.yaml' "
        % os.path.dirname(os.path.abspath(__file__)),
    )
    parser.add_argument(
        "--heartbeat",
        "-hb",
        action="store",
        default=None,
        help="Set the interval time to receive heartbeat messages to check that the bot is"
        + 'alive. Accepted strings are "hour", "day", "week". Defaults to None.',
    )
    args = parser.parse_args()

    # load config
    config_handle = args.config
    config = Config(config_handle.name)

    # check config
    notifiers = config.get("notifiers", list())
    if "mattermost" in notifiers and not config.get("mattermost", dict()).get("webhook_url"):
        __log__.error("No mattermost webhook configured. Starting like this would be pointless...")
        return
    if "telegram" in notifiers:
        if not config.get("telegram", dict()).get("bot_token"):
            __log__.error("No telegram bot token configured. Starting like this would be pointless...")
            return

    # Check for database configuration (required for multi-user mode)
    if not config.get("supabase"):
        __log__.error("No Supabase database configuration found. Multi-user mode requires database access.")
        return

    # get heartbeat instructions
    heartbeat_interval = args.heartbeat
    heartbeat = Heartbeat(config, heartbeat_interval)

    # adjust log level, if required
    if config.get("verbose"):
        __log__.setLevel(logging.DEBUG)
        __log__.debug("Settings from config: %s", pformat(config))

    # start hunting for flats in multi-user mode
    launch_flat_hunt_multi_user(config, heartbeat)


if __name__ == "__main__":
    main()
