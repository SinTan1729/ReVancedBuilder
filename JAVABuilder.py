import os
import sys
import configparser as cp
import json
from Cleanup import clean_exit
import subprocess

# Build the revanced apps
def build_apps(appstate):
    build_config = appstate['build_config']
    flag = appstate['flag']
    print = appstate['logger'].info

    chosen_patches = cp.ConfigParser()
    chosen_patches.read('chosen_patches.toml')

    try:
        included_patches = json.loads(chosen_patches['patches']['included'])
    except:
        included_patches = []
    try:
        excluded_patches = json.loads(chosen_patches['patches']['excluded'])
    except Exception as e:
        excluded_patches = []
    
    for app in build_config:
        # Check if we need to build an app
        if not build_config[app].getboolean('build'):
            continue

        # Build the command to be run
        cmd = 'java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar'

        try:
            root = build_config[app].getboolean('root')
        except:
            root = False
        
        if root:
            cmd += ' --mount -e microg-support'

        for item in included_patches:
            cmd += f" -i {item}"
        for item in excluded_patches:
            cmd += f" -e {item}"
        
        if flag == 'experimental':
            cmd += ' --experimental'
        
        try:
            keystore = build_config[app]['keystore']
            if not root:
                cmd += f" --keystore {keystore}"
        except:
            pass

        try:
            apk = build_config[app]['apk']
            pretty_name = build_config[app]['pretty_name']
            apkpure_appname = build_config[app]['apkpure_appname']
            output_name = build_config[app]['output_name']
        except:
            clean_exit(f"Invalid config for {app} in build_config.toml!", appstate)
        
        cmd += f" -a {apk}.apk -o {output_name}.apk"

        if root:
            print(f"Building {pretty_name} (root)...")
        else:
            print(f"Building {pretty_name} (nonroot)...")
        
        try:
            with subprocess.Popen(cmd, shell=True, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout as output:
                for line in output:
                    line_utf = line.decode('utf-8').strip('\n')
                    if line_utf:
                        print(line_utf)
        except Exception as e:
            clean_exit(f"There was an error while building {pretty_name}!\n{e}", appstate)
        
        try:
            os.rename(output_name+'.apk', output_name+'.apk') # TODO: Add timestamp here
        except FileNotFoundError:
            clean_exit(f"There was an error while building {pretty_name}!", appstate)
        