#!/usr/bin/env python3\

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra@ou.edu>
# SPDX-License-Identifier: GPL-3.0-only

import os
import sys
import json

from packaging.version import Version
import requests as req
from bs4 import BeautifulSoup as bs

from ReVancedBuilder.Cleanup import clean_exit

# Determine the best version available to download
def apkpure_best_match(version, soup):
    try:
        vers_list = [Version(x['data-dt-version']) for x in soup.css.select(f"a[data-dt-apkid^=\"b/APK/\"]")]
    except:
        clean_exit(f"    There was some error getting list of versions of {apk}...", appstate)
    
    if version != '0':
        vers_list = filter(lambda x: x <= Version(version), vers_list)
    
    return str(max(vers_list))

# Download an apk from APKPure.com
def apkpure_dl(apk, appname, version, hard_version, session, present_vers, flag):
    res = session.get(f"https://apkpure.com/{appname}/{apk}/versions")
    res.raise_for_status()
    soup = bs(res.text, 'html.parser')

    if not hard_version:
        version = apkpure_best_match(version, soup)
    
    if flag == 'checkonly' and present_vers[apk] != version:
        print(f"{apk} has an update ({present_vers[apk]} -> {version})")
        return

    try:
        if present_vers[apk] == version and flag != 'force' and os.path.isfile(apk+'.apk'):
            print(f"Recommended version {version} of {apk} is already present.")
            return
    except KeyError:
        pass
    print(f"  Downloading {apk} version {version}...")

    # Get the version code
    try:
        ver_code = soup.css.select(f"a[data-dt-version=\"{version}\"][data-dt-apkid^=\"b/APK/\"]")[0]['data-dt-versioncode']
    except:
        clean_exit(f"    There was some error while downloading {apk}...", appstate)
    
    res = session.get(f"https://d.apkpure.com/b/APK/{apk}?versionCode={ver_code}", stream=True)
    res.raise_for_status()
    with open(apk+'.apk', 'wb') as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)
    print("    Done!")



# Download apk files, if needed
def get_apks(appstate):
    present_vers = appstate['present_vers']
    build_config = appstate['build_config']
    flag=appstate['flag']

    print('Downloading required apk files from APKPure...')

    # Get latest patches using the ReVanced API
    try:
        patches = req.get('https://releases.revanced.app/patches').json()
    except req.exceptions.RequestException as e:
        clean_exit(e, appstate)
    
    session = req.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'})

    for app in build_config:
        # Check if we need to build an app
        if not build_config[app].getboolean('build'):
            continue

        try:
            apk = build_config[app]['apk']
            pretty_name = build_config[app]['pretty_name']
            apkpure_appname = build_config[app]['apkpure_appname']
        except:
            clean_exit(f"Invalid config for {app} in build_config.toml!", appstate)

        print(f"Checking {pretty_name}...")
        try:
            required_ver = build_config[app]['version']
            required_ver[0]
            hard_version = True
            print(f"Using version {required_ver} of {app} from ")
        except:
            hard_version = False
            compatible_vers = []
            for patch in patches:
                for pkg in patch['compatiblePackages']:
                    if pkg['name'] == apk:
                        try:
                            compatible_vers.append(pkg['versions'][-1])
                        except IndexError:
                            pass

            if not compatible_vers:
                required_ver = Version('0')
            else:
                required_ver = min(map(lambda x: Version(x), compatible_vers))

        apkpure_dl(apk, apkpure_appname, str(required_ver), hard_version, session, present_vers, flag)

        present_vers.update({apk: str(required_ver)})
    
    appstate['present_vers'] = present_vers
    return appstate