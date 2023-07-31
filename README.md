# Revanced Builder
This repo will allow one to build [ReVanced](https://github.com/revanced/) apps automatically and post it to a telegram channel to access and possibly share the builds with friends. It uses [Gotify](https://gotify.net), [ntfy.sh](https://ntfy.sh) or [telegram.sh](https://github.com/fabianonline/telegram.sh) to send messages and [telegram-upload](https://github.com/Nekmo/telegram-upload) to upload files (optionally, disabled out by default). Make sure that `Java >=17` is installed and selected as default.

## How to use
Just run `./build_revanced <working-directory> (force/clean/experimental/checkonly/buildonly)`. Might be a good idea to set it up to run periodically. There are a few ways of doing it.
1. Just drop it inside `/etc/cron.daily/`.
1. To make it run at a specific time (6AM in the example) using `cron`, put this in your `crontab`:
    ```crontab
    0 6 * * * <full-script-location> <full-working-directory-location>
    ```
1. The exact same thing as in 2 can be achieved using `systemd` timers instead. Create the following files.
    ```toml
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
    ExecStart=_JAVA_OPTIONS='-Xmx512m' <full-script-location> <full-working-directory-location>
    ```
    ```toml
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
    ```bash
    sudo systemctl enable --now revanced-builder.timer
    ```

## Notes
- The following programs are needed to run this script. Make sure that you have them in your `$PATH`.
    ```
    htmlq jq wget java curl
    ```
- To enable build for a particular apk, copy the `build_settings` file to your working directory and modify it to suit your needs.
- The script will download the **automatically selected compatible version** (using compatibility of patches as listed [here](https://github.com/revanced/revanced-patches#list-of-available-patches)) of Youtube on APKPure, **NOT** latest official version on Google Play.
- Under **NO CIRCUMSTANCES** any APKs will be uploaded to this repository to avoid DMCA.
- If you enable the Gotify, ntfy or telegram notifications or uploads, make sure to fill up the config options inside the `build_settings` file. For more information about the config, take at look at the repos of `telegram.sh` and `telegram-upload` provided above.
- It can also run a post script (if exists) called `post_script.sh`. The `timestamp` is passed as `$1`.
- In the current configuration, the script only builds YouTube ReVanced and YouTube Music ReVanced (both nonroot), but it's easy to add support for any other ReVanced app. The code for root builds is included but disabled by default.
- All the packages are pulled from [APKPure](https://apkpure.com) and GitHub (the `revanced/*` repos).

## Customize your build
If you wish to continue with the default settings, you may skip this step.

By default this will build ReVanced with ALL available patches. Follow [this guide](PATCHES_GUIDE.md) to exclude/customizing patches for your build.
