import grp
import json
import os
import pwd
import subprocess
import time
from os.path import join

import requests

DEFAULT_USER = "nobody"
HACKSPORTS_ROOT = "/opt/hacksports/"
COMPETITORS_GROUP = "competitors"

config_file = join(HACKSPORTS_ROOT, "config.json")
config = json.loads(open(config_file).read())
SERVER = config["web_server"]
TIMEOUT = 5

pamh = None


def run_login(user, password):
    r = requests.post(
        SERVER + "/api/user/login",
        data={
            "username": user,
            "password": password
        },
        timeout=TIMEOUT)
    return str(json.loads(r.text)['message'])


def display(string):
    message = pamh.Message(pamh.PAM_TEXT_INFO, string)
    pamh.conversation(message)


def prompt(string):
    message = pamh.Message(pamh.PAM_PROMPT_ECHO_OFF, string)
    return pamh.conversation(message)


def server_user_exists(user):
    result = run_login(user, "`&/")
    return result == "Incorrect password"


def secure_user(user):
    home = pwd.getpwnam(user).pw_dir

    # Append only bash history
    subprocess.check_output(['touch', os.path.join(home, '.bash_history')])
    subprocess.check_output(
        ['chown', 'root:' + user,
         os.path.join(home, '.bash_history')])
    subprocess.check_output(
        ['chmod', '660', os.path.join(home, '.bash_history')])
    subprocess.check_output(
        ['chattr', '+a', os.path.join(home, '.bash_history')])

    # Secure bashrc
    subprocess.check_output([
        'cp', '/opt/hacksports/config/securebashrc',
        os.path.join(home, '.bashrc')
    ])
    subprocess.check_output(
        ['chown', 'root:' + user,
         os.path.join(home, '.bashrc')])
    subprocess.check_output(['chmod', '755', os.path.join(home, '.bashrc')])
    subprocess.check_output(['chattr', '+a', os.path.join(home, '.bashrc')])

    # Secure profile
    subprocess.check_output(
        ['chown', 'root:' + user,
         os.path.join(home, '.profile')])
    subprocess.check_output(['chmod', '755', os.path.join(home, '.profile')])
    subprocess.check_output(['chattr', '+a', os.path.join(home, '.profile')])

    # User should not own their home directory
    subprocess.check_output(["chown", "root:" + user, home])
    subprocess.check_output(["chmod", "1770", home])


def pam_sm_authenticate(pam_handle, flags, argv):
    global pamh
    pamh = pam_handle

    try:
        user = pamh.get_user(None)
    except (pamh.exception, e):
        return e.pam_result

    try:
        entry = pwd.getpwnam(user)
        group = grp.getgrnam(COMPETITORS_GROUP)
        # local account exists and server account exists
        if server_user_exists(user) and user in group.gr_mem:
            response = prompt("Enter your password: ")
            result = run_login(user, response.resp)

            if "Successfully logged in" in result:
                return pamh.PAM_SUCCESS
        else:
            return pamh.PAM_USER_UNKNOWN

    # local user account does not exist
    except KeyError as e:
        try:
            if server_user_exists(user):
                subprocess.check_output([
                    "/usr/sbin/useradd", "-m", "-G", COMPETITORS_GROUP, "-s",
                    "/bin/bash", user
                ])
                secure_user(user)

                display("Welcome {}!".format(user))
                display("Your shell server account has been created.")
                prompt("Please press enter and reconnect.")

                # this causes the connection to close
                return pamh.PAM_SUCCESS
            else:
                display("Please make an account on the web site first.")
                return pamh.PAM_USER_UNKNOWN

        except Exception as e:
            pass

    return pamh.PAM_AUTH_ERR
