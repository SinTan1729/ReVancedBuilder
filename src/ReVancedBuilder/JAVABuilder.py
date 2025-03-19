#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra689@gmail.com>
# SPDX-License-Identifier: GPL-3.0-only

import configparser as cp
import json
import os
import subprocess

from ReVancedBuilder.Cleanup import err_exit

# Build the revanced apps


def build_apps(appstate):
    build_config = appstate["build_config"]
    flag = appstate["flag"]
    print = appstate["logger"].info

    chosen_patches = cp.ConfigParser()
    chosen_patches.read("chosen_patches")

    try:
        included_patches = json.loads(chosen_patches["patches"]["included"])
    except (KeyError, ValueError):
        included_patches = []
    try:
        excluded_patches = json.loads(chosen_patches["patches"]["excluded"])
    except (KeyError, ValueError):
        excluded_patches = []

    for app in build_config:
        # Check if we need to build an app
        if not build_config[app].getboolean("build"):
            continue

        # Build the command to be run
        cmd = "java -jar revanced-cli.jar patch -p revanced-patches.rvp"

        try:
            root = build_config[app].getboolean("root")
        except cp.Error:
            root = False

        if root:
            cmd += ' --mount -e "GmsCore support"'

        for item in included_patches:
            cmd += f" -i {item}"
        for item in excluded_patches:
            cmd += f" -e {item}"

        if flag == "experimental":
            cmd += " --experimental"

        try:
            keystore = build_config[app]["keystore"]
            if not root:
                cmd += f" --keystore {keystore} --keystore-entry-alias=alias --keystore-entry-password=ReVanced --keystore-password=ReVanced"
        except KeyError:
            pass

        try:
            apk = build_config[app]["apk"]
            pretty_name = build_config[app]["pretty_name"]
            output_name = build_config[app]["output_name"]
        except KeyError:
            err_exit(f"Invalid config for {app} in build_config!", appstate)

        cmd += f" -o {output_name}.apk {apk}.apk"

        if root:
            print(f"Building {pretty_name} (root) using '{cmd}'")
        else:
            print(f"Building {pretty_name} (nonroot) using '{cmd}'")

        try:
            with subprocess.Popen(
                cmd, shell=True, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            ).stdout as output:
                for line in output:
                    line_utf = line.decode("utf-8").strip("\n")
                    if line_utf:
                        print(line_utf)
        except Exception as e:
            err_exit(f"There was an error while building {pretty_name}!\n{e}", appstate)

        try:
            os.rename(output_name + ".apk", output_name + ".apk")
        except FileNotFoundError:
            err_exit(f"There was an error while building {pretty_name}!", appstate)
