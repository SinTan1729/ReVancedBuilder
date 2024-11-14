#!/usr/bin/env python3\

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra689@gmail.com>
# SPDX-License-Identifier: GPL-3.0-only

import os

from packaging.version import Version
import cloudscraper as scraper
from bs4 import BeautifulSoup as bs

from ReVancedBuilder.Cleanup import err_exit

# Determine the best version available to download


def apkpure_best_match(version, soup):
    try:
        vers_list_str = [x['data-dt-version'] for x in soup.css.select(f"a[data-dt-apkid^=\"b/APK/\"]")]
    except:
        err_exit(
            f"    There was some error getting list of versions of {apk}...", appstate)

    vers_list = map(lambda x: Version(x), vers_list_str)

    if version != '0':
        vers_list = filter(lambda x: x <= Version(version), vers_list)

    max_ver = max(vers_list)
    return next(filter(lambda x: Version(x) ==  max_ver, vers_list_str))

# Download an apk from apkpure.net


def apkpure_dl(apk, appname, version, hard_version, session, present_vers, flag):
    res = session.get(f"https://apkpure.com/{appname}/{apk}/versions")
    res.raise_for_status()
    soup = bs(res.text, 'html.parser')

    try:
        if present_vers[apk] == version and flag != 'force' and os.path.isfile(apk+'.apk'):
            print(
                f"Recommended version {version} of {apk} is already present.")
            return
    except KeyError:
        pass

    if not hard_version:
        apkpure_version = apkpure_best_match(version, soup)
        if version not in [apkpure_version, '0']:
            print(
                f"Required version {version} not found in APKPure, choosing version {apkpure_version} instead.")
        version = apkpure_version
        try:
            if present_vers[apk] == version and flag != 'force' and os.path.isfile(apk+'.apk'):
                print(
                    f"Recommended version {version} of {apk} is already present.")
                return
        except KeyError:
            pass

    if flag == 'checkonly' and present_vers[apk] != version:
        print(f"{apk} has an update ({present_vers[apk]} -> {version})")
        return

    print(f"  Downloading {apk} version {version}...")

    # Get the version code
    try:
        ver_code = soup.css.select(
            f"a[data-dt-version=\"{version}\"][data-dt-apkid^=\"b/APK/\"]")[0]['data-dt-versioncode']
    except:
        err_exit(
            f"    There was some error while downloading {apk}...", appname)

    res = session.get(
        f"https://d.apkpure.com/b/APK/{apk}?versionCode={ver_code}", stream=True)
    res.raise_for_status()
    with open(apk+'.apk', 'wb') as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)
    print("    Done!")


# Download apk files, if needed
def get_apks(appstate):
    present_vers = appstate['present_vers']
    build_config = appstate['build_config']
    flag = appstate['flag']

    print('Downloading required apk files from APKPure...')

    # Create a cloudscraper session
    session = scraper.create_scraper()

    # Get latest patches using the ReVanced API
    try:
        # Get the first result
        patches = session.get('https://api.revanced.app/v4/patches/list').json()
    except session.exceptions.RequestException as e:
        err_exit(f"Error fetching patches, {e}", appstate)

    for app in build_config:
        # Check if we need to build an app
        if not build_config[app].getboolean('build'):
            continue

        try:
            apk = build_config[app]['apk']
            pretty_name = build_config[app]['pretty_name']
            apkpure_appname = build_config[app]['apkpure_appname']
        except:
            err_exit(f"Invalid config for {app} in build_config!", appstate)

        print(f"Checking {pretty_name}...")
        try:
            required_ver = build_config[app]['version']
            hard_version = True
            print(f"Using version {required_ver} of {apk} from build_config.")
        except:
            hard_version = False
            compatible_vers = []
            for patch in patches:
                try:
                    compatible_vers.append(patch['compatiblePackages'][apk][-1])
                except (KeyError, TypeError):
                    pass

            if not compatible_vers:
                required_ver = Version('0')
            else:
                required_ver = min(map(lambda x: Version(x), compatible_vers))
                required_ver = next(filter(lambda x: Version(x) ==  required_ver, compatible_vers))

            print(f"Chosen required version of {apk} is {required_ver}.")

        if apk in appstate['present_vers'] and appstate['present_vers'][apk] == required_ver:
            print("It's already present on disk, so skipping download.")
        else:
            apkpure_dl(apk, apkpure_appname, required_ver,
                hard_version, session, present_vers, flag)

        present_vers.update({apk: required_ver})

    appstate['present_vers'] = present_vers
    return appstate
