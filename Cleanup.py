import os
import sys
from Notifications import send_notif

# Move apps to proper location
def move_apps(appstate):
    build_config = appstate['build_config']

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
        
        files = []
        dir = os.scandir('archive')
        for f in dir:
            if name in f.name:
                files.append(f)
        files.sort(key=lambda f: f.stat().st_ctime)
        files.reverse()
        for f in files[3:]:
            os.remove(f)
            print('Deleted old build '+f.name)
        dir.close()

def clean_exit(msg, appstate, code=1):
    send_notif(appstate, error=True)
    if msg:
        print(msg, file=sys.stderr)
    exit(code)