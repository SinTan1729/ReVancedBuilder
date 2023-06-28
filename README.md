# Revanced Builder
This repo will allow one to build [ReVanced](https://github.com/revanced/) apps automatically and post it to a telegram channel to access and possibly share the builds with friends. It uses [Gotify](https://gotify.net), [ntfy.sh](https://ntfy.sh) or [telegram.sh](https://github.com/fabianonline/telegram.sh) to send messages and [telegram-upload](https://github.com/Nekmo/telegram-upload) to upload files (optionally, disabled out by default). Make sure that `Java >=17` is installed and selected as default.

## How to use
Just run `./build_revanced <working-directory> (force/clean/experimental/checkonly)`. Might be a good idea to set it up to run periodically using cron. I currently use the following in a user crontab to run it everyday at 6 AM:
```
0 6 * * * <full-script-location> <full-working-directory-location>
```

## Notes
- To enable build for a particular apk, copy the `build_settings` file to your working directory and modify it to suit your needs.
- The script will download the **automatically selected compatible version** (using compatibility of patches as listed [here](https://github.com/revanced/revanced-patches#list-of-available-patches)) of Youtube on APKMirror, **NOT** latest official version on Google Play.
- Under **NO CIRCUMSTANCES** any APKs will be uploaded to this repository to avoid DMCA.
- If you enable the Gotify, ntfy or telegram notifications or uploads, make sure to fill up the config options inside the `build_settings` file. For more information about the config, take at look at the repos of `telegram.sh` and `telegram-upload` provided above.
- It can also run a post script (if exists) called `post_script.sh`. The `timestamp` is passed as `$1`.
- In the current configuration, the script only builds YouTube ReVanced and YouTube Music ReVanced (both nonroot), but it's easy to add support for any other ReVanced app. The code for root builds is included but disabled by default.
- All the packages are pulled from [APKMirror](https://apkmirror.com) and GitHub (the `revanced/*` repos).

## Customize your build
If you wish to continue with the default settings, you may skip this step.

By default this will build ReVanced with ALL available patches. Follow [this guide](PATCHES_GUIDE.md) to exclude/customizing patches for your build.
