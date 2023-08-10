#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra@ou.edu>
# SPDX-License-Identifier: GPL-3.0-only

import os
import sys
from Notifications import send_notif
import time

# Move apps to proper location
def move_apps(appstate):
    build_config = appstate['build_config']
    print = appstate['logger'].info

    try:
        os.mkdir('archive')
    except FileExistsError:
        pass

    for app in build_config:
        if not build_config[app].getboolean('build'):
            continue
        name = build_config[app]['output_name']
        final_name = f"{name}_{appstate['timestamp']}.apk"

        try:
            os.rename(name+'.apk', 'archive/'+final_name)
        except FileNotFoundError:
            pass
            # sys.exit('There was an error moving the final apk files!')
        
        # Do some cleanup, keep only the last 3 build's worth of files and a week worth of logs
        with os.scandir('archive') as dir:
            files = []
            for f in dir:
                if name in f.name:
                    files.append(f)
            files.sort(key=lambda f: f.stat().st_ctime)
            files.reverse()
            for f in files[3:]:
                os.remove(f)
                print('Deleted old build '+f.name)

        # Delete logs older than 7 days
        with os.scandir('logs') as dir:
            now = time.time()
            for f in dir:
                if f.stat().st_ctime < now - 7 * 86400:
                    os.remove(f)

def clean_exit(msg, appstate, code=1):
    print = appstate['logger'].info

    try:
        appstate['notification_config']
        send_notif(appstate, error=True)
    except:
        pass
    
    if msg:
        print(msg)
        
    # Delete the lockfile
    os.remove('lockfile')
    exit(code)