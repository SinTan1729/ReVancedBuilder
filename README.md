# Revanced Builder
This repo will allow one to build [ReVanced](https://github.com/revanced/) apps automatically and post it to a telegram channel to access and possibly share the builds with friends. It uses [telegram.sh](https://github.com/fabianonline/telegram.sh) to send messages and [telegram-upload](https://github.com/Nekmo/telegram-upload) to upload files (optionally, commented out by default). Make sure that `Java >=17` is installed and selected as default.

## How to use
Just run `./build_revanced <working-directory> (force/clean/experimental/checkonly)`. Might be a good idea to set it up to run periodically using cron. I currently use the following in a user crontab to run it everyday at 6 AM:
```
0 6 * * * <full-script-location> <full-working-directory-location>
```

## Notes
- The script will download the **automatically selected compatible version** (using compatibility of patches as listed [here](https://github.com/revanced/revanced-patches#list-of-available-patches)) of Youtube on APKMirror, **NOT** latest official version on Google Play.
- Under **NO CIRCUMSTANCES** any APKs will be uploaded to this repository to avoid DMCA.
- The script assumes that the working directory has the `telegram.sh` script along with a working config file and optionally `telegram-upload` installed and working with the channel link saved in a file called `channel_address`. For their config, look at the links provided on top.
- It can also run a post script (if exists) called `post_script.sh`. The `timestamp` would is passed as `$1`.
- In the current configuration, the script only builds YouTube ReVanced and YouTube Music ReVanced (both nonroot), but it's easy to add support for any other ReVanced app. The code for root builds is included but commented out.
- All the packages are pulled from [APKMirror](https://apkmirror.com) and GitHub (the `revanced/*` repos).

## Customize your build
If you wish to continue with the default settings, you may skip this step.

By default this will build ReVanced with ALL available patches. Follow [this guide](PATCHES_GUIDE.md) to exclude/customizing patches for your build.
