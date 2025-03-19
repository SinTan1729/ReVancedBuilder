#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra689@gmail.com>
# SPDX-License-Identifier: GPL-3.0-only

import json
import re
import subprocess

import requests as req


def send_notif(appstate, error=False):
    print = appstate["logger"].info
    timestamp = appstate["timestamp"]

    if error:
        msg = f"There was an error during build! Please check the logs.\nTimestamp: {timestamp}"
    else:
        build_config = appstate["build_config"]
        present_vers = appstate["present_vers"]

        msg = json.dumps(present_vers, indent=0)
        msg = re.sub('("|\{|\}|,)', "", msg).strip("\n")

        msg = msg.replace("revanced-", "ReVanced ")
        msg = msg.replace("cli", "CLI")
        msg = msg.replace("integrations", "Integrations")
        msg = msg.replace("patches", "Patches")

        for app in build_config:
            if not build_config[app].getboolean("build"):
                continue
            msg = msg.replace(build_config[app]["apk"], build_config[app]["pretty_name"])

        msg += "\nTimestamp: " + timestamp
        if appstate["gmscore_updated"]:
            msg += "\nGmsCore was updated."

    config = appstate["notification_config"]
    for entry in config:
        if not config[entry].getboolean("enabled"):
            continue
        encoded_title = "⚙⚙⚙ ReVanced Build ⚙⚙⚙".encode("utf-8")

        if entry == "ntfy":
            print("Sending notification through ntfy.sh...")
            try:
                url = config[entry]["url"]
                topic = config[entry]["topic"]
            except KeyError:
                print("URL or TOPIC not provided!")
                continue
            headers = {
                "Icon": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Revanced-logo-round.svg/240px-Revanced-logo-round.svg.png",
                "Title": encoded_title,
            }
            try:
                token = config[entry]["token"]
                headers["Authorization"] = "Bearer " + token
            except KeyError:
                continue
            try:
                req.post(f"{url}/{topic}", msg, headers=headers)
            except Exception as ex:
                print(f"Failed with exception: {ex}")

        elif entry == "gotify":
            print("Sending notification through Gotify...")
            try:
                url = config[entry]["url"]
                token = config[entry]["token"]
            except KeyError:
                print("URL or TOKEN not provided!")
                continue
            data = {"Title": encoded_title, "message": msg, "priority": "5"}
            try:
                req.post(f"{url}/message?token={token}", data)
            except Exception as e:
                print("Failed!" + str(e))

        elif entry == "telegram":
            print("Sending notification through Telegram...")
            try:
                chat = config[entry]["chat"]
                token = config[entry]["token"]
            except KeyError:
                print("CHAT or TOKEN not provided!")
                continue
            cmd = f'./telegram.sh -t {token} -c {chat} -T {encoded_title} -M "{msg}"'
            try:
                with subprocess.Popen(
                    cmd, shell=True, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                ).stdout as output:
                    for line in output:
                        line_utf = line.decode("utf-8").strip("\n")
                        if line_utf:
                            print(line_utf)
            except Exception as ex:
                print(f"Failed to send notification with exception: {ex}")

        else:
            print("Don't know how to send notifications to " + entry)
