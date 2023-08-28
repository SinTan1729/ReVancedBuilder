#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra@ou.edu>
# SPDX-License-Identifier: GPL-3.0-only

import sys
import os
import configparser as cp
import json
import logging
import subprocess

import requests as req
from packaging.version import Version
from datetime import datetime

from ReVancedBuilder.APKPure_dl import apkpure_best_match, apkpure_dl, get_apks
from ReVancedBuilder.JAVABuilder import build_apps
from ReVancedBuilder.Notifications import send_notif
from ReVancedBuilder.Cleanup import move_apps, err_exit

# Update the ReVanced tools, if needed
def update_tools(appstate):
    for item in ['revanced-cli', 'revanced-integrations', 'revanced-patches']:
        print(f"Checking updates for {item}...")
        tools = appstate['tools']
        *_, tool = filter(lambda x: x['repository'] == 'revanced/'+item, tools) # Get the last result
        latest_ver = Version(tool['version'])

        try:
            present_ver = Version(appstate['present_vers'][item])
        except KeyError:
            present_ver = Version('0')

        output_file = item+os.path.splitext(tool['name'])[1]
        if  flag == 'force' or not os.path.isfile(output_file) or present_ver < latest_ver:
            appstate['up-to-date'] = False
            print(f"{item} has an update ({str(present_ver)} -> {str(latest_ver)})")
            if flag != 'checkonly':
                print(f"Downloading {output_file}...")
                res = req.get(tool['browser_download_url'], stream=True)
                res.raise_for_status()
                with open(output_file, 'wb') as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                appstate['present_vers'].update({item: str(latest_ver)})
                print("Done!")

    return appstate

# Update microG, if needed
def update_microg(appstate):
    print('Checking updates for Vanced microG...')
    try:
        data = req.get('https://api.github.com/repos/inotia00/VancedMicroG/releases/latest').json()['tag_name']
        latest_ver = Version(data)
    except req.exceptions.RequestException as e:
        err_exit(f"Error fetching info about Vanced microG, {e}", appstate)

    try:
        present_ver = Version(appstate['present_vers']['VancedMicroG'])
    except KeyError:
        present_ver = Version('0')

    if flag == 'force' or not os.path.isfile('microg.apk') or present_ver < latest_ver:
            appstate['up-to-date'] = False
            print(f"Vanced microG has an update ({str(present_ver)} -> {str(latest_ver)})")
            if flag != 'checkonly':
                print(f"Downloading vanced-microg.apk...")
                res = req.get('https://github.com/inotia00/VancedMicroG/releases/latest/download/microg.apk', stream=True)
                res.raise_for_status()
                with open('microg.apk', 'wb') as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                appstate['present_vers'].update({'VancedMicroG': str(latest_ver)})
                print("Done!")
                appstate['microg_updated'] = True

    return appstate

# ------------------------------
# The main function starts here
# ------------------------------

# Create a dict for storing important data
appstate = {}

# Get a timestamp
time = datetime.now()
appstate['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')

# Read arguments
try:
    os.chdir(sys.argv[1])
except IndexError:
    sys.exit('Please provide a working directory as argument!')
except FileNotFoundError:
    sys.exit('Invalid working directory provided!')

# Try to make sure only one instance is running in a given working directory
try:
    if os.path.exists('lockfile'):
        raise FileExistsError
    with open('tmplockfile', 'x') as f:
        f.flush()
        os.fsync(f.fileno())
    os.replace('tmplockfile', 'lockfile')
except FileExistsError:
    sys.exit('Another instance is already running in the same working directory!')

# Set up logging
try:
    os.mkdir('logs')
except FileExistsError:
    pass

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()
logger.addHandler(logging.FileHandler(f"logs/{appstate['timestamp']}.log", 'w'))
print = logger.info
appstate['logger'] = logger

# Get the flag
try:
    flag = sys.argv[2]
except:
    flag = None

if flag not in ['buildonly', 'checkonly', 'force', 'experimental', None]:
        err_exit(f"Unknown flag: {flag}", appstate)

appstate['flag'] = flag
appstate['microg_updated'] = False

print(f"Started building ReVanced apps at {time.strftime('%d %B, %Y %H:%M:%S')}")
print('----------------------------------------------------------------------')

# Read configs
try:
    appstate['build_config']=cp.ConfigParser()
    appstate['build_config'].read_file(open('build_config', 'r'))
except FileNotFoundError:
    err_exit('No build config provided, exiting. Please look at the GitHub page for more information:\n  https://github.com/SinTan1729/ReVancedBuilder', appstate)

appstate['notification_config'] = cp.ConfigParser()
appstate['notification_config'].read('notification_config')

# Pull the latest information using the ReVanced API
try:
    tools = req.get('https://api.revanced.app/tools').json()['tools']
    appstate['tools'] = tools
except req.exceptions.RequestException as e:
    err_exit(f"Error fetching patch list, {e}", appstate)

try:
    with open('versions.json', 'r') as f:
        appstate['present_vers'] = json.load(f)
except:
    # We'll treat empty as 0 later
    appstate['present_vers'] = json.loads('{}')

appstate['up-to-date'] = True
# send_notif(appstate, error=False) # <,,,,,,,,<,,,,,,,,,,,,,
if flag != 'buildonly':
    appstate = update_tools(appstate)
    appstate = update_microg(appstate)
    if not appstate['up-to-date'] or flag == 'force':
        appstate = get_apks(appstate)

if (flag != 'checkonly' and not appstate['up-to-date']) or flag in ['force', 'buildonly']:
    build_apps(appstate)
    move_apps(appstate)

# Update version numbers in the versions.json file
if appstate['up-to-date'] and flag != 'buildonly':
    print('There\'s nothing to do.')
elif flag != 'checkonly':
    send_notif(appstate)
    try:
        os.rename('versions.json', 'versions-old.json')
    except FileNotFoundError:
        pass

    if flag != 'buildonly':
        with open('versions.json', 'w') as f:
            json.dump(appstate['present_vers'], f, indent=4)
        try:
            subprocess.run(
                f"{appstate['build_config']['post_script']['file']} {appstate['timestamp']}", shell=True)
        except:
            pass

# Delete the lockfile
os.remove('lockfile')

sys.exit(0)
