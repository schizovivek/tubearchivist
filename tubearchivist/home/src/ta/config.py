"""
Functionality:
- read and write config
- load config variables into redis
"""

import json
import os
import re

from celery.schedules import crontab
from home.src.ta.ta_redis import RedisArchivist


class AppConfig:
    """handle user settings and application variables"""

    def __init__(self, user_id=False):
        self.user_id = user_id
        self.config = self.get_config()
        self.colors = self.get_colors()

    def get_config(self):
        """get config from default file or redis if changed"""
        config = self.get_config_redis()
        if not config:
            config = self.get_config_file()

        if self.user_id:
            key = f"{self.user_id}:page_size"
            page_size = RedisArchivist().get_message(key)["status"]
            if page_size:
                config["archive"]["page_size"] = page_size

        config["application"].update(self.get_config_env())
        return config

    def get_config_file(self):
        """read the defaults from config.json"""
        with open("home/config.json", "r", encoding="utf-8") as f:
            config_file = json.load(f)

        config_file["application"].update(self.get_config_env())

        return config_file

    @staticmethod
    def get_config_env():
        """read environment application variables"""
        host_uid_env = os.environ.get("HOST_UID")
        if host_uid_env:
            host_uid = int(host_uid_env)
        else:
            host_uid = False

        host_gid_env = os.environ.get("HOST_GID")
        if host_gid_env:
            host_gid = int(host_gid_env)
        else:
            host_gid = False

        es_pass = os.environ.get("ELASTIC_PASSWORD")
        es_user = os.environ.get("ELASTIC_USER", default="elastic")

        application = {
            "REDIS_HOST": os.environ.get("REDIS_HOST"),
            "es_url": os.environ.get("ES_URL"),
            "es_auth": (es_user, es_pass),
            "HOST_UID": host_uid,
            "HOST_GID": host_gid,
        }

        return application

    @staticmethod
    def get_config_redis():
        """read config json set from redis to overwrite defaults"""
        config = RedisArchivist().get_message("config")
        if not list(config.values())[0]:
            return False

        return config

    def update_config(self, form_post):
        """update config values from settings form"""
        config = self.config
        for key, value in form_post.items():
            to_write = value[0]
            if len(to_write):
                if to_write == "0":
                    to_write = False
                elif to_write == "1":
                    to_write = True
                elif to_write.isdigit():
                    to_write = int(to_write)

                config_dict, config_value = key.split("_", maxsplit=1)
                config[config_dict][config_value] = to_write

        RedisArchivist().set_message("config", config, expire=False)

    @staticmethod
    def set_user_config(form_post, user_id):
        """set values in redis for user settings"""
        for key, value in form_post.items():
            to_write = value[0]
            if len(to_write):
                if to_write.isdigit():
                    to_write = int(to_write)
                message = {"status": to_write}
                redis_key = f"{user_id}:{key}"
                RedisArchivist().set_message(redis_key, message, expire=False)

    def get_colors(self):
        """overwrite config if user has set custom values"""
        colors = False
        if self.user_id:
            col_dict = RedisArchivist().get_message(f"{self.user_id}:colors")
            colors = col_dict["status"]

        if not colors:
            colors = self.config["application"]["colors"]

        self.config["application"]["colors"] = colors
        return colors

    def load_new_defaults(self):
        """check config.json for missing defaults"""
        default_config = self.get_config_file()
        redis_config = self.get_config_redis()

        # check for customizations
        if not redis_config:
            return

        needs_update = False

        for key, value in default_config.items():
            # missing whole main key
            if key not in redis_config:
                redis_config.update({key: value})
                needs_update = True
                continue

            # missing nested values
            for sub_key, sub_value in value.items():
                if sub_key not in redis_config[key].keys():
                    redis_config[key].update({sub_key: sub_value})
                    needs_update = True

        if needs_update:
            RedisArchivist().set_message("config", redis_config, expire=False)


class ScheduleBuilder:
    """build schedule dicts for beat"""

    SCHEDULES = {
        "update_subscribed": "0 8 *",
        "download_pending": "0 16 *",
        "check_reindex": "0 12 *",
        "thumbnail_check": "0 17 *",
        "run_backup": "0 18 0",
    }
    CONFIG = ["check_reindex_days", "run_backup_rotate"]

    def __init__(self):
        self.config = AppConfig().config

    def update_schedule_conf(self, form_post):
        """process form post"""
        print("processing form, restart container for changes to take effect")
        redis_config = self.config
        for key, value in form_post.items():
            to_check = value[0]
            if key in self.SCHEDULES and to_check:
                try:
                    to_write = self.value_builder(key, to_check)
                except ValueError:
                    print(f"failed: {key} {to_check}")
                    mess_dict = {
                        "status": "message:setting",
                        "level": "error",
                        "title": "Scheduler update failed.",
                        "message": "Invalid schedule input",
                    }
                    RedisArchivist().set_message("message:setting", mess_dict)
                    return

                redis_config["scheduler"][key] = to_write
            if key in self.CONFIG and to_check:
                redis_config["scheduler"][key] = int(to_check)
        RedisArchivist().set_message("config", redis_config, expire=False)
        mess_dict = {
            "status": "message:setting",
            "level": "info",
            "title": "Scheduler changed.",
            "message": "Please restart container for changes to take effect",
        }
        RedisArchivist().set_message("message:setting", mess_dict)

    def value_builder(self, key, to_check):
        """validate single cron form entry and return cron dict"""
        print(f"change schedule for {key} to {to_check}")
        if to_check == "0":
            # deactivate this schedule
            return False
        if re.search(r"[\d]{1,2}\/[\d]{1,2}", to_check):
            # number/number cron format will fail in celery
            print("number/number schedule formatting not supported")
            raise ValueError

        keys = ["minute", "hour", "day_of_week"]
        if to_check == "auto":
            # set to sensible default
            values = self.SCHEDULES[key].split()
        else:
            values = to_check.split()

        if len(keys) != len(values):
            print(f"failed to parse {to_check} for {key}")
            raise ValueError("invalid input")

        to_write = dict(zip(keys, values))
        try:
            int(to_write["minute"])
        except ValueError as error:
            print("too frequent: only number in minutes are supported")
            raise ValueError("invalid input") from error

        return to_write

    def build_schedule(self):
        """build schedule dict as expected by app.conf.beat_schedule"""
        schedule_dict = {}

        for schedule_item in self.SCHEDULES:
            item_conf = self.config["scheduler"][schedule_item]
            if not item_conf:
                continue

            minute = item_conf["minute"]
            hour = item_conf["hour"]
            day_of_week = item_conf["day_of_week"]
            schedule_name = f"schedule_{schedule_item}"
            to_add = {
                schedule_name: {
                    "task": schedule_item,
                    "schedule": crontab(
                        minute=minute, hour=hour, day_of_week=day_of_week
                    ),
                }
            }
            schedule_dict.update(to_add)

        return schedule_dict
