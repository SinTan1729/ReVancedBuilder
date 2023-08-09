#!/usr/bin/env python3

import sys
import os
import configparser as cp
import requests as req
import json
from packaging.version import Version
from APKPure_dl import *

# Update the ReVanced tools, if needed
def update_tools():
    for item in ['revanced-cli', 'revanced-integrations', 'revanced-patches']:
        *_, tool = filter(lambda x: x['repository'] == 'revanced/'+item, tools) # Get the last result
        latest_ver = Version(tool['version'])

        try:
            present_ver = Version(present_vers[item])
        except KeyError:
            present_ver = Version('0')

        if present_ver < latest_ver:
            global up_to_date
            up_to_date = False
            print(f"{item} has an update ({str(present_ver)} -> {str(latest_ver)})")
            output_file = item.split('-')[1]+os.path.splitext(tool['name'])[1]
            if flag != 'checkonly':
                print(f"Downloading {output_file}...")
                res = req.get(tool['browser_download_url'], stream=True)
                res.raise_for_status()
                with open(output_file, 'wb') as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                present_vers.update({item: str(latest_ver)})
                print("Done!")

# Update microG, if needed
def update_microg():
    try:
        data = req.get('https://api.github.com/repos/inotia00/VancedMicroG/releases/latest').json()['tag_name']
        latest_ver = Version(data)
    except req.exceptions.RequestException as e:
        sys.exit(e)

    try:
        present_ver = Version(present_vers['VancedMicroG'])
    except KeyError:
        present_ver = Version('0')

    if present_ver < latest_ver:
            global up_to_date
            up_to_date = False
            print(f"Vanced microG has an update ({str(present_ver)} -> {str(latest_ver)})")
            if flag != 'checkonly':
                print(f"Downloading microg.apk...")
                res = req.get('https://github.com/inotia00/VancedMicroG/releases/latest/download/microg.apk', stream=True)
                res.raise_for_status()
                with open('microg.apk', 'wb') as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                present_vers.update({'VancedMicroG': str(latest_ver)})
                print("Done!")

# Read configs
try:
    os.chdir(sys.argv[1])
except IndexError:
    sys.exit('Please provide a working directory as argument!')
except FileNotFoundError:
    sys.exit('Invalid working directory provided!')

try:
    flag = sys.argv[2]
except:
    flag = None

try:
    build_config=cp.ConfigParser()
    build_config.read_file(open('build_config.toml', 'r'))
except FileNotFoundError:
    sys.exit('No build config provided, exiting. Please look at the GitHub page for more information:\n  https://github.com/SinTan1729/ReVancedBuilder')

notification_config = cp.ConfigParser()
notification_config.read('notification_config.toml')

# Pull the latest information using the ReVanced API
try:
    tools = req.get('https://releases.revanced.app/tools').json()['tools']
except req.exceptions.RequestException as e:
    sys.exit(e)

global present_vers
try:
    with open('versions.json', 'r') as f:
        present_vers = json.load(f)
except:
    # We'll treat empty as 0 later
    present_vers = json.loads('{}')

global up_to_date
up_to_date = True

if flag != 'buildonly':
    update_tools()
    update_microg()
    # if not up_to_date:
    present_vers = get_apks(present_vers, build_config)

# if (flag != 'checkonly' and not up_to_date) or flag == 'force':
#     build_apps()

# Update version numbers in the versions.json file
if up_to_date:
    print('There\'s nothing to do.')
elif flag != 'checkonly':
    with open('versions.json', 'w') as f:
        json.dump(present_vers, f, indent=4)
