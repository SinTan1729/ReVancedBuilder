# Revanced Builder
This repo will allow one to build [ReVanced](https://github.com/revanced/) apps automatically, send notifications (and possibly share the builds with friends). It uses [Gotify](https://gotify.net), [ntfy.sh](https://ntfy.sh) or [telegram.sh](https://github.com/fabianonline/telegram.sh) to send messages. Make sure that `Java >=17` is installed and selected as default.

## Installation
Recommended way is to use [`pipx`](https://github.com/pypa/pipx) to install the program.
```
pipx install git+https://github.com/SinTan1729/ReVancedBuilder
```
And then you can update/reinstall the program using `pipx reinstall ReVancedBuilder`.
## How to use
Just run `ReVancedBuilder <working-directory> (force/experimental/checkonly/buildonly)`.

It might be a good idea to set it up to run periodically. There are a few ways of doing it.
1. Just drop it inside `/etc/cron.daily/`.
1. To make it run at a specific time (6AM in the example) using `cron`, put this in your `crontab`:
    ```
    0 6 * * * <program-full-location> <full-working-directory-location>
    ```
1. The exact same thing as in 2 can be achieved using `systemd` timers instead. Create the following files.
    ```
    /etc/systemd/system/revanced-builder.service
    ---------------------------------------------
    [Unit]
    Description=Automatically build new builds of ReVanced
    Wants=network-online.target
    After=network-online.target

    [Service]
    Type=oneshot
    User=<user>
    Group=<group>
    # Environment="_JAVA_OPTIONS=-Xmx512m" # optional, useful if experiencing crashes due to low memory
    ExecStart=<program-full-location> <full-working-directory-location>
    ```
    ```
    /etc/systemd/system/revanced-builder.timer
    -------------------------------------------
    [Unit]
    Description=Automatically build new builds of ReVanced

    [Timer]
    OnCalendar=*-*-* 6:00:00

    [Install]
    WantedBy=timers.target
    ```
    and then enable the timer using
    ```
    sudo systemctl enable --now revanced-builder.timer
    ```

## Notes
- If you installed it using `pipx`, you can figure out the full location of the program by running `which ReVancedBuilder`.
- This app needs some config files to run. Download all the config files inside `example_configs` directory, namely `build_config`, `chosen_patches` (optional), and `notification_config` (optional, needed only if you want to send notifications) and move them to your working directory. Then, you should modify these files to your liking.
- The script will download the **automatically selected compatible version** (unless version is specified in `build_config`) (using compatibility of patches as listed [here](https://revanced.app/patches)) of Youtube on APKPure, **NOT** latest official version on Google Play.
- **Under no circumstances** will any APKs be uploaded to this repository as that might attract legal problems.
- If you enable telegram notifications, make sure to fill up the config options inside the `build_config` file. For more information about the config, take at look at the repos of `telegram.sh` and `telegram-upload` provided above.
- It can also run a post script (if exists), specified in the `build_config` file. The `timestamp` is passed as `$1`.
- In the current configuration, the script only builds YouTube ReVanced and YouTube Music ReVanced (both nonroot), but it's easy to add support for any other ReVanced app using the `build_config` file. The config files are self-explanatory.
- All the packages are pulled from [APKPure](https://apkpure.com) and GitHub (the [`revanced/*`](https://github.com/revanced) repos).

