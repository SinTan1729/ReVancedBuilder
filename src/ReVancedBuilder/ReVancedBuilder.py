#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra689@gmail.com>
# SPDX-License-Identifier: GPL-3.0-only

import configparser as cp
import json
import logging
import os
import subprocess
import sys
import hashlib
from datetime import datetime
import requests as req
from packaging.version import Version

from ReVancedBuilder.APKPure_dl import get_apks
from ReVancedBuilder.Cleanup import err_exit, move_apps, send_notif
from ReVancedBuilder.JAVABuilder import build_apps


def update_signatures(appstate):
    try:
        data = req.get("https://api.revanced.app/v5/patches").json()
    except req.exceptions.RequestException as e:
        err_exit(f"Error fetching information about revanced-patches signature, {e}", appstate)
    url = data["signature_download_url"]

    output_file = "revanced-patches.rvp.asc"
    print("Updating signature for revanced patches.")
    res = req.get(url, stream=True)
    res.raise_for_status()
    with open(output_file, "wb") as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)

    print("Updating the GPG signature.")
    res = req.get("https://api.revanced.app/v5/patches/keys")
    res.raise_for_status()
    data = res.json()
    key = data["patches_public_key"]
    with open("revanced-keys.gpg", "w") as f:
        f.write(key)

    print("Updating the attestations.")
    with open("revanced-patches.rvp", "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    res = req.get(
        f"https://api.github.com/repos/revanced/revanced-patches/attestations/sha256:{file_hash}"
    )
    res.raise_for_status()
    data = res.json()
    bundle = data["attestations"][0]["bundle"]
    with open("revanced-patches.rvp.sigstore.json", "w") as f:
        json.dump(bundle, f)

    print("Done!")


# Update the ReVanced tools, if needed
def update_tools(appstate):
    tools = {}
    for item in ["revanced-cli", "revanced-patches", "GmsCore"]:
        try:
            data = req.get(f"https://api.github.com/repos/revanced/{item}/releases/latest").json()
        except req.exceptions.RequestException as e:
            err_exit(f"Error fetching information about {item}, {e}", appstate)

        assets = filter(
            lambda a: not a["browser_download_url"].endswith((".asc", "-hw-signed.apk")),
            data["assets"],
        )
        url = next(assets)["browser_download_url"]

        tools[item] = {
            "version": data["tag_name"],
            "browser_download_url": url,
        }

    for item in tools.keys():
        print(f"Checking updates for {item}...")
        tool = tools[item]
        latest_ver = Version(tool["version"])

        try:
            present_ver = Version(appstate["present_vers"][item])
        except KeyError:
            present_ver = Version("0")

        extension = tool["browser_download_url"].rsplit(".", 1)[-1]
        output_file = f"{item}.{extension}"
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

    appstate["tools"] = tools
    return appstate


def sync_json(appstate, need_to_build):
    appstate["present_vers"]["need_to_build"] = need_to_build
    with open("versions.json", "w") as f:
        json.dump(appstate["present_vers"], f, indent=4)


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

# Read current local versions
try:
    with open("versions.json", "r") as f:
        appstate["present_vers"] = json.load(f)
except FileNotFoundError:
    # We'll treat empty as 0 later
    appstate["present_vers"] = json.loads("{}")

appstate["up-to-date"] = True

need_to_build = appstate.get("present_vers", {}).get("need_to_build", False)
if flag != "buildonly":
    appstate = update_tools(appstate)
    if not appstate["up-to-date"] and flag != "checkonly":
        try:
            os.rename("versions.json", "versions-old.json")
        except FileNotFoundError:
            pass
        sync_json(appstate, True)
    if (not appstate["up-to-date"] and flag != "checkonly") or flag == "force" or need_to_build:
        appstate = get_apks(appstate)
        update_signatures(appstate)
        sync_json(appstate, True)

if (
    (flag != "checkonly" and not appstate["up-to-date"])
    or flag in ["force", "buildonly"]
    or need_to_build
):
    build_apps(appstate)
    move_apps(appstate)

# Update version numbers in the versions.json file
if appstate["up-to-date"] and flag != "buildonly" and (not need_to_build):
    print("There's nothing to do.")
elif flag != "checkonly":
    sync_json(appstate, False)
    if flag != "buildonly":
        try:
            cmd = f"{appstate['build_config']['post_script']['file']} {appstate['timestamp']}"
            print(f"Running the post command '{cmd}'")
            subprocess.run(cmd, shell=True)
        except Exception as ex:
            print(f"Got exception while running the post-command: '{ex}'")
            err_exit("", appstate, 0)

    send_notif(appstate)

# Delete the lockfile
os.remove("lockfile")

sys.exit(0)
