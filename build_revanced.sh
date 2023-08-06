#!/usr/bin/env bash

# Run only one instance of this script at one time
[ "${BKLOCKER}" != "running" ] && exec env BKLOCKER="running" flock -en "/tmp/revanced-builder.lock" "$0" "$@" || :

# Get timestamp
timestamp=$(date '+%Y%m%d%H%M%S')

# Log everything to a logfile inside logs/
log_file="$1/logs/$timestamp.log"
[ -d "$1" ] && mkdir -p "$1/logs" && exec > >(tee "$log_file") 2>&1

# Set working directory and current directory
if [ -d "$1" ]; then
    WDIR="$1"
else
    echo "Working directory not provided"
    exit 1
fi

# File containing all patches
patch_file="$WDIR/chosen_patches.txt"

# Returns if $1 is less than $2
ver_less_than() {
    # Strip letters from version name
    ver1=$(echo $1 | sed 's/[a-zA-Z]*//g')
    ver2=$(echo $2 | sed 's/[a-zA-Z]*//g')
    [ $(echo $ver1$'\n'$ver2 | sort -V | tail -n1) != $ver1 ] && echo true || echo false
}

# Make sure to work in the script directory
SDIR="$(dirname -- "$(readlink -f -- "$0")")"
cd "$SDIR"

# Read the settings
if [ -f "$WDIR/build_settings" ]; then
    source "$WDIR/build_settings"
else
    if [ -f "./build_settings"]; then
        cp ./build_settings "$WDIR/build_settings"
        source ./build_settings
    else
        echo "Could not find the build_settings file!"
    fi
fi

# Get line numbers where included & excluded patches start from.
# We rely on the hardcoded messages to get the line numbers using grep
excluded_start="$(grep -n -m1 'EXCLUDE PATCHES' "$patch_file" | cut -d':' -f1)"
included_start="$(grep -n -m1 'INCLUDE PATCHES' "$patch_file" | cut -d':' -f1)"

# Get everything but hashes from between the EXCLUDE PATCH & INCLUDE PATCH line
# Note: '^[^#[:blank:]]' ignores starting hashes and/or blank characters i.e, whitespace & tab excluding newline
excluded_patches="$(tail -n +$excluded_start $patch_file | head -n "$((included_start - excluded_start))" | grep '^[^#[:blank:]]')"

# Get everything but hashes starting from INCLUDE PATCH line until EOF
included_patches="$(tail -n +$included_start $patch_file | grep '^[^#[:blank:]]')"

# Array for storing patches
declare -a patches

# Required artifacts in the format repository-name_filename
artifacts="revanced/revanced-cli:revanced-cli.jar revanced/revanced-integrations:revanced-integrations.apk revanced/revanced-patches:revanced-patches.jar inotia00/VancedMicroG:microg.apk"

## Functions

# Function for populating patches array, using a function here reduces redundancy & satisfies DRY principals
populate_patches() {
    # Note: <<< defines a 'here-string'. Meaning, it allows reading from variables just like from a file
    while read -r patch; do
        patches+=("$1 $patch")
    done <<<"$2"
}

## Main

# cleanup to fetch new revanced on next run
if [[ "$2" == "clean" ]]; then
    rm -f revanced-cli.jar revanced-integrations.apk revanced-patches.jar
    exit
fi

if [[ "$2" == "experimental" ]]; then
    EXPERIMENTAL="--experimental"
fi

# Set flag to determine if a build should happen or not
flag=false
check_flag=false

# Get inside the working directory
cd "$WDIR"
echo "$(date) | Starting check..."

if [[ $2 != buildonly ]]; then
    # Create a new versions file, if needed
    [ -f versions.json ] || echo "{}" >versions.json
    cp versions.json versions-new.json
    # Fetch all the dependencies
    try=0
    while :; do
        try=$(($try + 1))
        [ $try -gt 10 ] && echo "API error!" && exit 2
        curl -s -X 'GET' 'https://releases.revanced.app/tools' -H 'accept: application/json' -o latest_versions.json
        cat latest_versions.json | jq -e '.error' >/dev/null || break
        echo "API failure, trying again. $((10 - $try)) tries left..."
        sleep 10
    done

    for artifact in $artifacts; do
        #Check for updates
        repo=$(echo $artifact | cut -d ':' -f1)
        name=$(echo $artifact | cut -d ':' -f2)
        basename=$(echo $repo | cut -d '/' -f2)
        echo "Checking $basename"
        version_present=$(jq -r ".\"$basename\"" versions.json)
        [[ "$version_present" == "null" ]] && version_present=0
        data="$(jq -r ".tools[] | select((.repository == \"$repo\") and (.content_type | contains(\"archive\")))" latest_versions.json)"
        [[ $name == microg.apk ]] && version=$(curl -s "https://api.github.com/repos/$repo/releases/latest" | jq -r '.tag_name') || version=$(echo "$data" | jq -r '.version')
        if [[ $(ver_less_than $version_present $version) == true || ! -f $name || $2 == force ]]; then
            if [[ $2 == checkonly ]]; then
                echo "[checkonly] $basename has an update ($version_present -> $version)"
                check_flag=true
                continue
            fi
            echo "Downloading $name"
            [[ $name == microg.apk && -f $name && $2 != force ]] && microg_updated=true
            # shellcheck disable=SC2086,SC2046
            [[ $name == microg.apk ]] && download_link="https://github.com/$repo/releases/latest/download/$name" || download_link="$(echo "$data" | jq -r '.browser_download_url')"
            curl -sLo "$name" "$download_link"
            jq ".\"$basename\" = \"$version\"" versions-new.json >versions.json.tmp && mv versions.json.tmp versions-new.json
            echo "Upgraded $basename from $version_present to $version"
            flag=true
        fi
    done

    [[ ! -f com.google.android.youtube.apk || ! -f com.google.android.apps.youtube.music.apk ]] && flag=true

    # Exit if no updates happened
    if [[ $flag == false && $2 != force ]]; then
        if [[ $check_flag == false ]]; then
            echo "Nothing to update"
        else
            "$SDIR/download_apk.sh" "$WDIR" checkonly
        fi
        echo "--------------------"$'\n'"--------------------"
        exit
    fi

    # Download required apk files
    "$SDIR/download_apk.sh" "$WDIR"
fi

# If the variables are NOT empty, call populate_patches with proper arguments
[[ ! -z "$excluded_patches" ]] && populate_patches "-e" "$excluded_patches"
[[ ! -z "$included_patches" ]] && populate_patches "-i" "$included_patches"

# Variable to flag errors
error=0

# Functions for building the APKs

build_yt_nonroot() {
    echo "************************************"
    echo "Building YouTube APK"
    echo "************************************"
    if [ -f "com.google.android.youtube.apk" ]; then
        echo "Building Non-root APK"
        java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar \
            ${patches[@]} \
            $EXPERIMENTAL \
            -a com.google.android.youtube.apk -o revanced-yt-nonroot.apk
    else
        echo "Cannot find YouTube APK, skipping build"
    fi
    echo ""
    echo "************************************"

    # Rename files
    mv revanced-yt-nonroot.apk YouTube_ReVanced_nonroot_$timestamp.apk || error=1
}

build_yt_root() {
    echo "************************************"
    echo "Building YouTube APK"
    echo "************************************"
    if [ -f "com.google.android.youtube.apk" ]; then
        echo "Building Root APK"
        java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar --mount \
            -e microg-support ${patches[@]} \
            $EXPERIMENTAL \
            -a com.google.android.youtube.apk -o revanced-yt-root.apk
    else
        echo "Cannot find YouTube APK, skipping build"
    fi
    echo ""
    echo "************************************"

    # Rename files
    mv revanced-yt-root.apk YouTube_ReVanced_root_$timestamp.apk || error=1
}

build_ytm_nonroot() {
    echo "Building YouTube Music APK"
    echo "************************************"
    if [ -f "com.google.android.apps.youtube.music.apk" ]; then
        echo "Building Non-root APK"
        java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar \
            ${patches[@]} \
            $EXPERIMENTAL \
            -a com.google.android.apps.youtube.music.apk -o revanced-ytm-nonroot.apk
    else
        echo "Cannot find YouTube Music APK, skipping build"
    fi

    # Rename files
    mv revanced-ytm-nonroot.apk YouTube_Music_ReVanced_nonroot_$timestamp.apk || error=1
}

build_ytm_root() {
    echo "Building YouTube Music APK"
    echo "************************************"
    if [ -f "com.google.android.apps.youtube.music.apk" ]; then
        echo "Building Root APK"
        java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar --mount \
            -e microg-support ${patches[@]} \
            $EXPERIMENTAL \
            -a com.google.android.apps.youtube.music.apk -o revanced-ytm-root.apk
    else
        echo "Cannot find YouTube Music APK, skipping build"
    fi

    # Rename files
    mv revanced-ytm-root.apk YouTube_Music_ReVanced_root_$timestamp.apk || error=1
}

telegram_send_msg() {
    # telegram.sh uses bot account, but it supports formatted messages
    [[ "$TELEGRAM_TOKEN" == "" || "$TELEGRAM_CHAT" == "" ]] && echo "Please provide valid channel address in the settings!"
    ./telegram.sh -t "$TELEGRAM_TOKEN" -c "$TELEGRAM_CHAT" -T "⚙⚙⚙ Build Details ⚙⚙⚙" -M "$1"$'\n'"Timestamp: $timestamp"$'\n'"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
}

gotify_send_msg() {
    curl -s -X POST "$GOTIFY_URL/message?token=$GOTIFY_TOKEN" \
        -F "title=⚙⚙⚙ Build Details ⚙⚙⚙" -F "message=$1" -F "priority=5"
}

ntfy_send_msg() {
    curl -s -H "Icon: https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Revanced-logo-round.svg/240px-Revanced-logo-round.svg.png" \
        -H "Title: ⚙⚙⚙ ReVanced Build ⚙⚙⚙" \
        -d "$1" \
        "$NTFY_URL/$NTFY_TOPIC"
}

# Check the config and build accordingly
$YT_NONROOT && build_yt_nonroot
$YT_ROOT && build_yt_root
$YTM_NONROOT && build_ytm_nonroot
$YTM_ROOT && build_ytm_root

# Send telegram message about the new build

if [ $error == 1 ]; then
    echo "There was an error while building!"
    msg="There was an error during the build process! Please take a look at the logs."$'\n'"Timestamp: $timestamp"

    $TG_NOTIFICATIONS && telegram_send_msg "$msg"
    $GOTIFY_NOTIFICATIONS && gotify_send_msg "$msg"
    $NTFY_NOTIFICATIONS && ntfy_send_msg "$msg"

    [[ $2 != buildonly ]] && mv versions-new.json versions-fail.json || mv versions-new.json versions.json
    exit 4
fi

if $TG_UPLOAD; then
    echo "Uploading to telegram"
    # telegram-upload uses personal account, hence bypassing 50 MB max upload limit of bots
    [ "$CHANNEL_ADDRESS" == "" ] && echo "Please provide valid channel address in the settings!"
    /home/sintan/.local/bin/telegram-upload YouTube_ReVanced_nonroot_$timestamp.apk YouTube_Music_ReVanced_nonroot_$timestamp.apk --to "$CHANNEL_ADDRESS" --caption "" && sent=true
fi

# Create the message to be sent
msg=$(cat versions.json | tail -n+2 | head -n-1 | cut -c3- | sed "s/\"//g" | sed "s/,//g" | sed "s/com.google.android.apps.youtube.music/YouTube Music/" |
    sed "s/com.google.android.youtube/YouTube/" | sed "s/VancedMicroG/Vanced microG/" | sed "s/revanced-/ReVanced /g" | sed "s/patches/Patches/" |
    sed "s/cli/CLI/" | sed "s/integrations/Integrations/" | awk 1 ORS=$'\n') # I know, it's a hacky solution

if $TG_NOTIFICATIONS; then
    echo "Sending messages to telegram"
    telegram_send_msg "$msg"
    [ $microg_updated ] && telegram_send_msg "_An update of microg was published._"
fi

if $GOTIFY_NOTIFICATIONS; then
    echo "Sending messages to Gotify"
    MESSAGE="$msg"$'\n'"Timestamp: $timestamp"
    gotify_send_msg "$MESSAGE"
    [ $microg_updated ] && gotify_send_msg "An update of microg was published."
fi

if $NTFY_NOTIFICATIONS; then
    echo "Sending messages to ntfy.sh"
    MESSAGE="$msg"$'\n'"Timestamp: $timestamp"
    ntfy_send_msg "$MESSAGE"
    [ $microg_updated ] && ntfy_send_msg "An update of microg was published."
fi

# Do some cleanup, keep only the last 3 build's worth of files and a week worth of logs
mkdir -p archive
mv *ReVanced_*_$timestamp.apk archive/
find ./archive -maxdepth 1 -type f -printf '%Ts\t%P\n' |
    sort -rn |
    tail -n +7 |
    cut -f2- |
    xargs -r -I {} rm "./archive/{}"
find ./logs -mtime +7 -exec rm {} \;

# Run a custom post script, if available
[ -f post_script.sh ] && ./post_script.sh $timestamp

echo "Done!"$'\n'"************************************"
