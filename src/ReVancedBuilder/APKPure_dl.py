#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra689@gmail.com>
# SPDX-License-Identifier: GPL-3.0-only

import os
import re

import cloudscraper as scraper
from bs4 import BeautifulSoup as bs
from packaging.version import Version
from subprocess import check_output


from ReVancedBuilder.Cleanup import err_exit

# Determine the best version available to download


def apkpure_best_match(version, soup, appstate, apk):
    try:
        vers_list_str = [
            x["data-dt-version"] for x in soup.css.select('a[data-dt-apkid^="b/APK/"]')
        ]
    except Exception as ex:
        err_exit(f"    There was some error getting list of versions of {apk}: {ex}", appstate)

    vers_list = map(lambda x: Version(x), vers_list_str)

    if version != "0":
        vers_list = filter(lambda x: x <= Version(version), vers_list)

    max_ver = max(vers_list)
    return next(filter(lambda x: Version(x) == max_ver, vers_list_str))


# Download an apk from apkpure.net


def apkpure_dl(apk, appname, version, hard_version, session, present_vers, flag, appstate):
    try:
        res = session.get(f"https://apkpure.com/{appname}/{apk}/versions")
        soup = bs(res.text, "html.parser")
    except Exception as ex:
        err_exit(f"Could not get list of available versions from APKPure.: {ex}")

    try:
        if present_vers[apk] == version and flag != "force" and os.path.isfile(apk + ".apk"):
            print(f"Recommended version {version} of {apk} is already present.")
            return
    except KeyError:
        pass

    if not hard_version:
        apkpure_version = apkpure_best_match(version, soup, appstate, apk)
        if version not in [apkpure_version, "0"]:
            print(
                f"Required version {version} for {apk} not found in APKPure.\n",
                "This may happen due to IP blocking, or many other reasons.\n",
                f"Please download manually and put it as {apk}.apk inside the build directory.\n",
                "Try APKMirror, and make sure that it's not a split xapk file.\n",
                "Also update the versions.json file before retrying.",
            )
            err_exit(f"Could not download the required version for {apk}.", appstate)
        try:
            if present_vers[apk] == version and flag != "force" and os.path.isfile(apk + ".apk"):
                print(f"Recommended version {version} of {apk} is already present.")
                return
        except KeyError:
            pass

    if flag == "checkonly" and present_vers[apk] != version:
        print(f"{apk} has an update ({present_vers[apk]} -> {version})")
        return

    print(f"  Downloading {apk} version {version}...")

    # Get the version code
    try:
        ver_code = soup.css.select(f'a[data-dt-version="{version}"][data-dt-apkid^="b/APK/"]')[0][
            "data-dt-versioncode"
        ]
    except Exception as ex:
        err_exit(f"    There was some error while downloading {apk}: {ex}", appstate)

    res = session.get(f"https://d.apkpure.com/b/APK/{apk}?versionCode={ver_code}", stream=True)
    res.raise_for_status()
    with open(apk + ".apk", "wb") as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)
    print("    Done!")


# Parse patches output to JSON
def parse_patches(data):
    res = []

    for block in re.split(r"\n\s*\n", data.strip()):
        d = {
            "name": None,
            "compatible_packages": [],
        }

        pkg = None

        for line in block.splitlines():
            s = line.strip()

            if s.startswith("Name:"):
                d["name"] = s.split(":", 1)[1].strip()

            elif s.startswith("Package name:"):
                if pkg:
                    d["compatible_packages"].append(pkg)
                pkg = {"package_name": s.split(":", 1)[1].strip(), "compatible_versions": []}

            elif line.startswith("\t\t") and pkg:
                pkg["compatible_versions"].append(s)

        if pkg:
            d["compatible_packages"].append(pkg)

        if not d["compatible_packages"]:
            d["compatible_packages"] = None
        else:
            for p in d["compatible_packages"]:
                if not p["compatible_versions"]:
                    p["compatible_versions"] = None

        res.append(d)

    return res


# Download apk files, if needed
def get_apks(appstate):
    present_vers = appstate["present_vers"]
    build_config = appstate["build_config"]
    flag = appstate["flag"]

    print("Downloading required apk files from APKPure...")

    # Create a cloudscraper session
    session = scraper.create_scraper()

    # Get latest patches from the patches file
    try:
        patches = check_output(
            [
                "java",
                "-jar",
                "revanced-cli.jar",
                "list-patches",
                "-bp",
                "revanced-patches.rvp",
                "--packages",
                "--versions",
            ],
            text=True,
        )
        patches = parse_patches(patches)
    except Exception as ex:
        err_exit(f"Error fetching patches, {ex}", appstate)

    for app in build_config:
        # Check if we need to build an app
        if not build_config[app].getboolean("build"):
            continue

        try:
            apk = build_config[app]["apk"]
            pretty_name = build_config[app]["pretty_name"]
            apkpure_appname = build_config[app]["apkpure_appname"]
        except Exception as ex:
            err_exit(f"Invalid config for {app} in build_config!: {ex}", appstate)

        print(f"Checking {pretty_name}...")
        try:
            required_ver = build_config[app]["version"]
            hard_version = True
            # print(f"Using version {required_ver} of {apk} from build_config.")
        except KeyError:
            print("Trying to choose version.")
            hard_version = False
            version_sets = []
            for item in patches or []:
                for pkg in item.get("compatible_packages") or []:
                    if not pkg:
                        continue
                    if pkg.get("package_name") != apk:
                        continue
                    versions = set(
                        v for v in (pkg.get("compatible_versions") or []) if v is not None
                    )
                    if versions:  # only keep non-empty sets
                        version_sets.append(versions)

            compatible_vers = set.intersection(*version_sets) if version_sets else set()

            if not compatible_vers:
                required_ver = Version("0")
            else:
                required_ver = max(map(lambda x: Version(x), compatible_vers))
                required_ver = next(filter(lambda x: Version(x) == required_ver, compatible_vers))

            print(f"Chosen required version of {apk} is {required_ver}.")

        if apk in appstate["present_vers"] and appstate["present_vers"][apk] == required_ver:
            print("It's already present on disk, so skipping download.")
        else:
            apkpure_dl(
                apk,
                apkpure_appname,
                required_ver,
                hard_version,
                session,
                present_vers,
                flag,
                appstate,
            )

        present_vers.update({apk: required_ver})

    appstate["present_vers"] = present_vers
    return appstate
