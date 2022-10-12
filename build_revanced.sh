#!/bin/bash

# Use force to run the builds forcefully

# Get timestamp
timestamp=$(date '+%s')

# File containing all patches
patch_file="./patches.txt"

# Set working directory and current directory
if [ -d "$1" ]; then
    WDIR="$1"
else
    echo "Working directory not provided"
    exit -1
fi

ODIR="$PWD"

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

# Artifacts associative array aka dictionary
declare -A artifacts

artifacts["revanced-cli.jar"]="revanced/revanced-cli revanced-cli .jar"
artifacts["revanced-integrations.apk"]="revanced/revanced-integrations app-release-unsigned .apk"
artifacts["revanced-patches.jar"]="revanced/revanced-patches revanced-patches .jar"
artifacts["apkeep"]="EFForg/apkeep apkeep-x86_64-unknown-linux-gnu"

## Functions

get_artifact_download_url() {
    # Usage: get_download_url <repo_name> <artifact_name> <file_type>
    local api_url result
    api_url="https://api.github.com/repos/$1/releases/latest"
    # shellcheck disable=SC2086
    result=$(curl -s $api_url | jq ".assets[] | select(.name | contains(\"$2\") and contains(\"$3\") and (contains(\".sig\") | not)) | .browser_download_url")
    echo "${result:1:-1}"
}

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

# Get inside the working directory
cd "$WDIR"
echo "$(date) | Statring check..." | tee -a build.log

# Fetch all the dependencies
for artifact in "${!artifacts[@]}"; do
    #Check for updates
    name=$(echo "${artifacts[$artifact]}" | cut -d" " -f1)
    [[ "$name" == "EFForg/apkeep" && ! -f ./apkeep ]] && curl -sLo "$artifact" $(get_artifact_download_url ${artifacts[$artifact]}) && break
    version_present=$(jq -r ".\"$name\"" versions.json)
    version=$(curl -s "https://api.github.com/repos/$name/releases/latest" | grep -Eo '"tag_name": "v(.*)"' | sed -E 's/.*"v([^"]+)".*/\1/')

    if [[ ${version_present//[!0-9]/} -lt ${version//[!0-9]/} ]]; then
        echo "Downloading $artifact" | tee -a build.log
        # shellcheck disable=SC2086,SC2046
        curl -sLo "$artifact" $(get_artifact_download_url ${artifacts[$artifact]})
        jq ".\"$name\" = \"$version\"" versions.json > versions.json.tmp && mv versions.json.tmp versions.json
        flag=true
    fi
done

# Exit if no updates happened
if [[ $flag == false && "$2" != "force" ]]; then
    echo "Nothing to update" | tee -a build.log
    exit
fi

# Download required apk files
/bin/bash "$ODIR/download_apkmirror.sh" "$WDIR"

# Fetch microG
chmod +x apkeep

if [ ! -f "vanced-microG.apk" ]; then
    # Vanced microG 0.2.24.220220
    VMG_VERSION="0.2.24.220220"

    echo "Downloading Vanced microG" | tee -a build.log
    ./apkeep -a com.mgoogle.android.gms@$VMG_VERSION .
    mv com.mgoogle.android.gms@$VMG_VERSION.apk vanced-microG.apk
    jq ".\"vanced-microG\" = \"$VMG_VERSION\"" versions.json > versions.json.tmp && mv versions.json.tmp versions.json
fi

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
#        -a com.google.android.youtube.apk -o build/revanced-root.apk
    echo "Building Non-root APK" | tee -a build.log
    java -jar revanced-cli.jar -m revanced-integrations.apk -b revanced-patches.jar \
        ${patches[@]} \
        $EXPERIMENTAL \
        -a com.google.android.youtube.apk -o revanced.apk
else
    echo "Cannot find YouTube APK, skipping build" | tee -a build.log
fi
echo ""
echo "************************************"
echo "Building YouTube Music APK"
echo "************************************"
if [ -f "com.google.android.apps.youtube.music.apk" ]; then
#    echo "Building Root APK"
#    java -jar revanced-cli.jar -b revanced-patches.jar --mount \
#        -e microg-support ${patches[@]} \
#        $EXPERIMENTAL \
#        -a com.google.android.apps.youtube.music.apk -o build/revanced-music-root.apk
    echo "Building Non-root APK" | tee -a build.log
    java -jar revanced-cli.jar -b revanced-patches.jar \
        ${patches[@]} \
        $EXPERIMENTAL \
        -a com.google.android.apps.youtube.music.apk -o revanced-music.apk
else
    echo "Cannot find YouTube Music APK, skipping build" | tee -a build.log
fi

# Rename files
mv revanced.apk ReVanced-nonroot-$timestamp.apk
mv revanced-music.apk ReVanced-Music-nonroot-$timestamp.apk

# Send telegram message about the new build
echo "Sending messages to telegram" | tee -a build.log
/home/sintan/.local/bin/telegram-upload ReVanced-nonroot-$timestamp.apk ReVanced-Music-nonroot-$timestamp.apk --to "placeholder_for_channel_address" --caption ""
echo "<----------Build details---------->" > message.tmp
cat versions.json | tail -n+2 | head -n-1 | cut -c3- | sed "s/\"//g" | sed "s/,//g" | sed "s/com.google.android.apps.youtube.music/YouTube Music/" | sed "s/com.google.android.youtube/YouTube/" | sed "s/vanced-microG/Vanced microG/" >> message.tmp
cat message.tmp | ./telegram.sh -
rm message.tmp

# Do some cleanup
mkdir -p archive
mv ReVanced*.apk archive/
find archive/ -mtime +3 -exec rm {} \;
