"""
CTF API Configuration File

Note this is just a python script. It does config things.
"""

import datetime
import json

import api
import api.app
from api.common import WebException


# Helper class for timezones
class EST(datetime.tzinfo):

    def __init__(self, utc_offset):
        self.utc_offset = utc_offset

    def utcoffset(self, dt):
        return datetime.timedelta(hours=-self.utc_offset)

    def dst(self, dt):
        return datetime.timedelta(0)


# Competition Information Placeholder
competition_name = ""
competition_urls = [
    "",
]

""" CTF Settings
These are the default settings that will be loaded
into the database if no settings are already loaded.
"""
default_settings = {
    "enable_teachers":
    True,
    "enable_feedback":
    True,

    # TIME WINDOW
    "start_time":
    datetime.datetime.utcnow(),
    "end_time":
    datetime.datetime.utcnow(),

    # COMPETITION INFORMATION
    "competition_name": "",
    "competition_url": "",

    # EMAIL WHITELIST
    "email_filter": [],

    # TEAMS
    "max_team_size":
    1,

    # ACHIEVEMENTS
    "achievements": {
        "enable_achievements": True,
        "processor_base_path": "./achievements",
    },
    "username_blacklist": [
        "adm",
        "admin",
        "audio",
        "backup",
        "bin",
        "cdrom",
        "competitors",
        "crontab",
        "daemon",
        "dialout",
        "dip",
        "disk",
        "dnsmasq",
        "fax",
        "floppy",
        "games",
        "gnats",
        "hacksports",
        "input",
        "irc",
        "kmem",
        "list",
        "lp",
        "lxd",
        "mail",
        "man",
        "messagebus",
        "mlocate",
        "netdev",
        "news",
        "nobody",
        "nogroup",
        "operator",
        "plugdev",
        "pollinate",
        "proxy",
        "root",
        "sasl",
        "shadow",
        "shellinabox",
        "src",
        "ssh",
        "sshd",
        "staff",
        "sudo",
        "sync",
        "sys",
        "syslog",
        "tape",
        "tty",
        "ubuntu",
        "users",
        "utmp",
        "uucp",
        "uuidd",
        "vagrant",
        "vboxadd",
        "vboxsf",
        "video",
        "voice",
    ],

    # EMAIL (SMTP)
    "email": {
        "enable_email": False,
        "email_verification": False,
        "parent_verification_email": False,
        "smtp_url": "",
        "smtp_port": 587,
        "email_username": "",
        "email_password": "",
        "from_addr": "",
        "from_name": "",
        "max_verification_emails": 3,
        "smtp_security": "TLS"
    },

    # CAPTCHA
    "captcha": {
        "enable_captcha": False,
        "captcha_url": "https://www.google.com/recaptcha/api/siteverify",
        "reCAPTCHA_public_key": "",
        "reCAPTCHA_private_key": "",
    },

    # LOGGING
    # Will be emailed any severe internal exceptions!
    # Requires email block to be setup.
    "logging": {
        "admin_emails": ["ben@example.com", "joe@example.com"],
        "critical_error_timeout": 600
    },

    # SHELL SERVERS
    "shell_servers": {
        "enable_sharding": False,
        "default_stepping": 5000,
        "steps": [7500, 12500, 17500],
        "limit_added_range": False,
    }
}
""" Helper functions to get settings. Do not change these """


def get_settings():
    db = api.common.get_conn()
    settings = db.settings.find_one({}, {"_id": 0})

    if settings is None:
        db.settings.insert(default_settings)
        return default_settings

    return settings


def change_settings(changes):
    db = api.common.get_conn()
    settings = db.settings.find_one({})

    def check_keys(real, changed):
        keys = list(changed.keys())
        for key in keys:
            if key not in real:
                raise WebException("Cannot update setting for '{}'".format(key))
            elif type(real[key]) != type(changed[key]):
                raise WebException("Cannot update setting for '{}'".format(key))
            elif isinstance(real[key], dict):
                check_keys(real[key], changed[key])
                # change the key so mongo $set works correctly
                for key2 in changed[key]:
                    changed["{}.{}".format(key, key2)] = changed[key][key2]
                changed.pop(key)

    check_keys(settings, changes)

    db.settings.update({"_id": settings["_id"]}, {"$set": changes})
