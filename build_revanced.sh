#!/bin/bash

# Run only one instance of this script at one time
[ "${BKLOCKER}" != "running" ] && exec env BKLOCKER="running" flock -en "/tmp/revanced-builder.lock" "$0" "$@" || :

# Log everything to a logfile inside logs/
log_file="$1/logs/$(date '+%s')"
[ -d "$1" ] && mkdir -p "$1/logs" && exec > >(tee "$log_file") 2>&1

# Get timestamp
timestamp=$(date '+%s')

# Set working directory and current directory
if [ -d "$1" ]; then
    WDIR="$1"
else
    echo "Working directory not provided"
    exit -1
fi

# File containing all patches
patch_file="$WDIR./chosen_patches.txt"

# Returns if $1 is less than $2
ver_less_than() {
    # Strip letters from version name
    ver1=$(echo $1 | sed 's/[a-zA-Z]*//g')
    ver2=$(echo $2 | sed 's/[a-zA-Z]*//g')
    [ $(echo $ver1$'\n'$ver2 | sort -V | tail -n1) != $ver1 ] && echo true || echo false
}

# Make sure to work in the script directory
SDIR="$(dirname -- "$( readlink -f -- "$0"; )";)"
cd "$SDIR"

# Get line numbers where included & excluded patches start from. 
# We rely on the hardcoded messages to get the line numbers using grep
excluded_start="$(grep -n -m1 'EXCLUDE PATCHES' "$patch_file" | cut -d':' -f1)"
included_start="$(grep -n -m1 'INCLUDE PATCHES' "$patch_file" | cut -d':' -f1)"

# Get everything but hashes from between the EXCLUDE PATCH & INCLUDE PATCH line
# Note: '^[^#[:blank:]]' ignores starting hashes and/or blank characters i.e, whitespace & tab excluding newline
excluded_patches="$(tail -n +$excluded_start $patch_file | head -n "$(( included_start - excluded_start ))" | grep '^[^#[:blank:]]')"

# Get everything but hashes starting from INCLUDE PATCH line until EOF
included_patches="$(tail -n +$included_start $patch_file | grep '^[^#[:blank:]]')"

# Array for storing patches
declare -a patches

# # Artifacts associative array aka dictionary
# declare -A artifacts

# artifacts["revanced-cli.jar"]="revanced/revanced-cli revanced-cli .jar"
# artifacts["revanced-integrations.apk"]="revanced/revanced-integrations app-release-unsigned .apk"
# artifacts["revanced-patches.jar"]="revanced/revanced-patches revanced-patches .jar"
# artifacts["apkeep"]="EFForg/apkeep apkeep-x86_64-unknown-linux-gnu"

# Required artifacts in the format repository-name_filename
artifacts="revanced/revanced-cli:revanced-cli.jar revanced/revanced-integrations:revanced-integrations.apk revanced/revanced-patches:revanced-patches.jar TeamVanced/VancedMicroG:microg.apk"

## Functions

# get_artifact_download_url() {
#     # Usage: get_download_url <repo_name> <artifact_name> <file_type>
#     local api_url result
#     api_url="https://api.github.com/repos/$1/releases/latest"
#     # shellcheck disable=SC2086
#     result=$(curl -s $api_url | jq ".assets[] | select(.name | contains(\"$2\") and contains(\"$3\") and (contains(\".sig\") | not)) | .browser_download_url")
#     echo "${result:1:-1}"
# }

# Function for populating patches array, using a function here reduces redundancy & satisfies DRY principals
populate_patches() {
    # Note: <<< defines a 'here-string'. Meaning, it allows reading from variables just like from a file
    while read -r patch; do
        patches+=("$1 $patch")
    done <<< "$2"
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

# Fetch all the dependencies
curl -X 'GET' 'https://releases.rvcd.win/tools' -H 'accept: application/json' | sed 's:\\\/:\/:g' > latest_versions.json
for artifact in $artifacts; do
    #Check for updates
    repo=$(echo $artifact | cut -d ':' -f1)
    name=$(echo $artifact | cut -d ':' -f2)
    basename=$(echo $repo | cut -d '/' -f2)
    echo "Checking $basename"
    version_present=$(jq -r ".\"$basename\"" versions.json)
    data="$(jq -r ".tools[] | select((.repository == \"$repo\") and (.content_type | contains(\"archive\")))" latest_versions.json)"
    version=$(echo "$data" | jq -r '.version')
    if [[ $(ver_less_than $version_present $version) == true || ! -f $name || $2 == force ]]; then
        if [[ $2 == checkonly ]]; then
            echo "[checkonly] $basename has an update ($version_present -> $version)"
            check_flag=true
            continue
        fi
        echo "Downloading $name"
        [[ $name == microg.apk && -f $name && $2 != force ]] && microg_updated=true
        # shellcheck disable=SC2086,SC2046
        curl -sLo "$name" "$(echo "$data" | jq -r '.browser_download_url')"
        jq ".\"$basename\" = \"$version\"" versions.json > versions.json.tmp && mv versions.json.tmp versions.json
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
        "$SDIR/download_apkmirror.sh" "$WDIR" checkonly
    fi
    echo "--------------------"$'\n'"--------------------"
    exit
fi

# Download required apk files
"$SDIR/download_apkmirror.sh" "$WDIR" $2

# # Fetch microG
# chmod +x apkeep

# if [ ! -f "vanced-microG.apk" ]; then
#     # Vanced microG 0.2.24.220220
#     VMG_VERSION="0.2.24.220220"

#     echo "Downloading Vanced microG"
#     ./apkeep -a com.mgoogle.android.gms@$VMG_VERSION .
#     mv com.mgoogle.android.gms@$VMG_VERSION.apk vanced-microG.apk
#     jq ".\"vanced-microG\" = \"$VMG_VERSION\"" versions.json > versions.json.tmp && mv versions.json.tmp versions.json
# fi

# If the variables are NOT empty, call populate_patches with proper arguments
[[ ! -z "$excluded_patches" ]] && populate_patches "-e" "$excluded_patches"
[[ ! -z "$included_patches" ]] && populate_patches "-i" "$included_patches"

echo "************************************"
echo "Building YouTube APK"
echo "************************************"

if [ -f "com.google.android.youtube.apk" ]; then
#    echo "Building Root APK"
#    java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar --mount \
#        -e microg-support ${patches[@]} \
#        $EXPERIMENTAL \
#        -a com.google.android.youtube.apk -o build/revanced-yt-root.apk
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
echo "Building YouTube Music APK"
echo "************************************"
if [ -f "com.google.android.apps.youtube.music.apk" ]; then
#    echo "Building Root APK"
#    java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar --mount \
#        -e microg-support ${patches[@]} \
#        $EXPERIMENTAL \
#        -a com.google.android.apps.youtube.music.apk -o build/revanced-ytm-root.apk
    echo "Building Non-root APK"
    java -jar revanced-cli.jar -m revanced-integrations.apk  -b revanced-patches.jar \
        ${patches[@]} \
        $EXPERIMENTAL \
        -a com.google.android.apps.youtube.music.apk -o revanced-ytm-nonroot.apk
else
    echo "Cannot find YouTube Music APK, skipping build"
fi

# Rename files
mv revanced-yt-nonroot.apk YouTube_ReVanced_nonroot_$timestamp.apk
mv revanced-ytm-nonroot.apk YouTube_Music_ReVanced_nonroot_$timestamp.apk
# mv revanced-yt-root.apk YouTube_ReVanced_root_$timestamp.apk
# mv revanced-ytm-root.apk YouTube_Music_ReVanced_root_$timestamp.apk

# Send telegram message about the new build
echo "Sending messages to telegram"

# telegram-upload uses personal account, hence bypassing 50 MB max upload limit of bots
# channel_address=$(cat channel_address | sed -z '$ s/\n$//')
# /home/sintan/.local/bin/telegram-upload YouTube_ReVanced_nonroot_$timestamp.apk YouTube_Music_ReVanced_nonroot_$timestamp.apk --to "$channel_address" --caption "" && sent=true

# telegram.sh uses bot account, but it supports formatted messages
msg=$(cat versions.json | tail -n+2 | head -n-1 | cut -c3- | sed "s/\"//g" | sed "s/,//g" | sed "s/com.google.android.apps.youtube.music/YouTube Music/" \
        | sed "s/com.google.android.youtube/YouTube/" | sed "s/VancedMicroG/Vanced microG/" | sed "s/revanced-/ReVanced /g" | sed "s/patches/Patches/" \
        | sed "s/cli/CLI/" | sed "s/integrations/Integrations/" | awk 1 ORS=$'\n') # I know, it's a hacky solution
# [ $sent ] && 
./telegram.sh -T "⚙⚙⚙ Build Details ⚙⚙⚙" -M "$msg"$'\n'"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
[ $microg_updated ] && ./telegram.sh -M "_An update of microg was published. Please download it from the link in the pinned message._"

# Do some cleanup, keep only the last 3 build's worth of files and a week worth of logs
mkdir -p archive
mv YouTube_ReVanced_nonroot_$timestamp.apk archive/
mv YouTube_Music_ReVanced_nonroot_$timestamp.apk archive/
find ./archive -maxdepth 1 -type f -printf '%Ts\t%P\n' \
    | sort -rn \
    | tail -n +7 \
    | cut -f2- \
    | xargs -r -I {} rm "./archive/{}"
find ./logs -mtime +7 -exec rm {} \;

echo "Done!"$'\n'"************************************"