#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Sayantan Santra <sayantan.santra@ou.edu>
# SPDX-License-Identifier: GPL-3.0-only

import json
import re
import requests as req
import subprocess

def send_notif(appstate, error=False):
    print = appstate['logger'].info
    timestamp = appstate['timestamp']

    if error:
        msg = f"There was an error during build! Please check the logs.\nTimestamp: {timestamp}"
    else:
        notification_config = appstate['notification_config']
        build_config = appstate['build_config']
        present_vers = appstate['present_vers']
        flag = appstate['flag']

        msg = json.dumps(present_vers, indent=0)
        msg = re.sub('("|\{|\}|,)', '', msg).strip('\n')

        msg = msg.replace('revanced-', 'ReVanced ')
        msg = msg.replace('cli', 'CLI')
        msg = msg.replace('integrations', 'Integrations')
        msg = msg.replace('patches', 'Patches')
        msg = msg.replace('VancedMicroG', 'Vanced microG')

        for app in build_config:
            if not build_config[app].getboolean('build'):
                continue
            msg = msg.replace(build_config[app]['apk'], build_config[app]['pretty_name'])

        msg += '\nTimestamp: ' + timestamp
        if appstate['microg_updated']:
            msg += '\nVanced microG was updated.'

    config = appstate['notification_config']
    for entry in config:
        if not config[entry].getboolean('enabled'):
            continue
        encoded_title = '⚙⚙⚙ ReVanced Build ⚙⚙⚙'.encode('utf-8')

        match entry:
            case 'ntfy':
                print('Sending notification through ntfy.sh...')
                try:
                    url = config[entry]['url']
                    topic = config[entry]['topic']
                except:
                    print('URL or TOPIC not provided!')
                    continue
                headers = {'Icon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Revanced-logo-round.svg/240px-Revanced-logo-round.svg.png',
                            'Title': encoded_title}
                try:
                    req.post(f"{url}/{topic}", msg, headers=headers)
                except Exception as e:
                    print('Failed!' + str(e))

            case 'gotify':
                print('Sending notification through Gotify...')
                try:
                    url = config[entry]['url']
                    token = config[entry]['token']
                except:
                    print('URL or TOKEN not provided!')
                    continue
                data = {'Title': encoded_title, 'message': msg, 'priority': '5'}
                try:
                    req.post(f"{url}/message?token={token}", data)
                except Exception as e:
                    print('Failed!' + str(e))

            case 'telegram':
                print('Sending notification through Telegram...')
                try:
                    chat = config[entry]['chat']
                    token = config[entry]['token']
                except:
                    print('CHAT or TOKEN not provided!')
                    continue
                cmd = f"./telegram.sh -t {token} -c {chat} -T {encoded_title} -M \"{msg}\""
                try:
                    with subprocess.Popen(cmd, shell=True, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout as output:
                        for line in output:
                            line_utf = line.decode('utf-8').strip('\n')
                            if line_utf:
                                print(line_utf)
                except Exception as e:
                    clean_exit(f"Failed!\n{e}", appstate)

            case _:
                print('Don\'t know how to send notifications to ' + entry)
