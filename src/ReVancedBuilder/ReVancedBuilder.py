#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra689@gmail.com>
# SPDX-License-Identifier: GPL-3.0-only

import configparser as cp
import json
import logging
import os
import subprocess
import sys
from datetime import datetime

import requests as req
from packaging.version import Version

from ReVancedBuilder.APKPure_dl import get_apks
from ReVancedBuilder.Cleanup import err_exit, move_apps, send_notif
from ReVancedBuilder.JAVABuilder import build_apps


# Update the ReVanced tools, if needed
def update_tools(appstate):
    for item in ["revanced-cli", "revanced-patches"]:
        print(f"Checking updates for {item}...")
        tools = appstate["tools"]
        tool = next(
            filter(
                lambda x: x["repository"] == "revanced/" + item
                and x["content_type"] not in ["application/pgp-keys", "application/json"],
                tools,
            )
        )
        latest_ver = Version(tool["version"])

        try:
            present_ver = Version(appstate["present_vers"][item])
        except KeyError:
            present_ver = Version("0")

        output_file = item + os.path.splitext(tool["name"])[1]
        if flag == "force" or not os.path.isfile(output_file) or present_ver < latest_ver:
            appstate["up-to-date"] = False
            print(f"{item} has an update ({str(present_ver)} -> {str(latest_ver)})")
            if flag != "checkonly":
                print(f"Downloading {output_file}...")
                res = req.get(tool["browser_download_url"], stream=True)
                res.raise_for_status()
                with open(output_file, "wb") as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                appstate["present_vers"].update({item: str(latest_ver)})
                print("Done!")

    return appstate


# Update GmsCore, if needed
def update_gmscore(appstate):
    print("Checking updates for GmsCore...")
    # Pull the latest information using the ReVanced API
    try:
        data = req.get("https://api.revanced.app/v2/gmscore/releases/latest").json()["release"]
    except req.exceptions.RequestException as e:
        err_exit(f"Error fetching GmsCore information, {e}", appstate)

    latest_ver = Version(data["metadata"]["tag_name"])

    try:
        present_ver = Version(appstate["present_vers"]["GmsCore"])
    except KeyError:
        present_ver = Version("0")

    try:
        variant = appstate["build_config"]["gmscore"]["variant"]
    except KeyError:
        variant = "regular"

    if variant == "alt":
        gmscore_link = next(filter(lambda x: "-hw-" in x["name"], data["assets"]))[
            "browser_download_url"
        ]
    else:
        gmscore_link = next(filter(lambda x: "-hw-" not in x["name"], data["assets"]))[
            "browser_download_url"
        ]

    if flag == "force" or not os.path.isfile("GmsCore.apk") or present_ver < latest_ver:
        appstate["up-to-date"] = False
        print(f"GmsCore has an update ({str(present_ver)} -> {str(latest_ver)})")
        if flag != "checkonly":
            print("Downloading GmsCore...")
            res = req.get(gmscore_link, stream=True)
            res.raise_for_status()
            with open("GmsCore.apk", "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            appstate["present_vers"].update({"GmsCore": str(latest_ver)})
            print("Done!")
            appstate["gmscore_updated"] = True

    return appstate


# ------------------------------
# The main function starts here
# ------------------------------

# Create a dict for storing important data
appstate = {}

# Get a timestamp
time = datetime.now()
appstate["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

# Read arguments
try:
    os.chdir(sys.argv[1])
except IndexError:
    sys.exit("Please provide a working directory as argument!")
except FileNotFoundError:
    sys.exit("Invalid working directory provided!")

# Try to make sure only one instance is running in a given working directory
try:
    if os.path.exists("lockfile"):
        raise FileExistsError
    with open("tmplockfile", "x") as f:
        f.flush()
        os.fsync(f.fileno())
    os.replace("tmplockfile", "lockfile")
except FileExistsError:
    sys.exit("Another instance is already running in the same working directory!")

# Set up logging
try:
    os.mkdir("logs")
except FileExistsError:
    pass

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()
logger.addHandler(logging.FileHandler(f"logs/{appstate['timestamp']}.log", "w"))
print = logger.info
appstate["logger"] = logger

# Get the flag
try:
    flag = sys.argv[2]
except IndexError:
    flag = None

if flag not in ["buildonly", "checkonly", "force", "experimental", None]:
    err_exit(f"Unknown flag: {flag}", appstate)

appstate["flag"] = flag
appstate["gmscore_updated"] = False

print(f"Started building ReVanced apps at {time.strftime('%d %B, %Y %H:%M:%S')}")
print("----------------------------------------------------------------------")

# Read configs
try:
    appstate["build_config"] = cp.ConfigParser()
    appstate["build_config"].read_file(open("build_config", "r"))
except FileNotFoundError:
    err_exit(
        "No build config provided, exiting. Please look at the GitHub page for more information:\n  https://github.com/SinTan1729/ReVancedBuilder",
        appstate,
    )

appstate["notification_config"] = cp.ConfigParser()
appstate["notification_config"].read("notification_config")

# Pull the latest information using the ReVanced API
try:
    tools = req.get("https://api.revanced.app/tools").json()["tools"]
    appstate["tools"] = tools
except req.exceptions.RequestException as e:
    err_exit(f"Error fetching patch list, {e}", appstate)

try:
    with open("versions.json", "r") as f:
        appstate["present_vers"] = json.load(f)
except FileNotFoundError:
    # We'll treat empty as 0 later
    appstate["present_vers"] = json.loads("{}")

appstate["up-to-date"] = True

if flag != "buildonly":
    appstate = update_tools(appstate)
    appstate = update_gmscore(appstate)
    if (not appstate["up-to-date"] and flag != "checkonly") or flag == "force":
        appstate = get_apks(appstate)

if (flag != "checkonly" and not appstate["up-to-date"]) or flag in ["force", "buildonly"]:
    build_apps(appstate)
    move_apps(appstate)

# Update version numbers in the versions.json file
if appstate["up-to-date"] and flag != "buildonly":
    print("There's nothing to do.")
elif flag != "checkonly":
    try:
        os.rename("versions.json", "versions-old.json")
    except FileNotFoundError:
        pass

    if flag != "buildonly":
        with open("versions.json", "w") as f:
            json.dump(appstate["present_vers"], f, indent=4)
        try:
            cmd = f"{appstate['build_config']['post_script']['file']} {appstate['timestamp']}"
            print(f"Running the post command '{cmd}'")
            subprocess.run(cmd, shell=True)
        except Exception as ex:
            print(f"Got exception while running the build: '{ex}'")
            err_exit("", appstate, 0)

    send_notif(appstate)

# Delete the lockfile
os.remove("lockfile")

sys.exit(0)
