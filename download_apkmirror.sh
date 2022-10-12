#!/usr/bin/env bash

declare -A apks

apks["com.google.android.youtube"]=dl_yt
apks["com.google.android.apps.youtube.music"]=dl_ytm

## Functions

# Wget user agent
WGET_HEADER="User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"

# Wget function
req() { wget -nv -O "$2" --header="$WGET_HEADER" "$1"; }

# Wget apk verions
get_apk_vers() { req "$1" - | sed -n 's;.*Version:</span><span class="infoSlide-value">\(.*\) </span>.*;\1;p'; }

# Wget apk verions(largest)
get_largest_ver() {
	local max=0
	while read -r v || [ -n "$v" ]; do
		if [[ ${v//[!0-9]/} -gt ${max//[!0-9]/} ]]; then max=$v; fi
	done
	if [[ $max = 0 ]]; then echo ""; else echo "$max"; fi
}

# Wget download apk
dl_apk() {
	local url=$1 regexp=$2 output=$3
	url="https://www.apkmirror.com$(req "$url" - | tr '\n' ' ' | sed -n "s/href=\"/@/g; s;.*${regexp}.*;\1;p")"
	echo "$url" | tee -a build.log
	url="https://www.apkmirror.com$(req "$url" - | tr '\n' ' ' | sed -n 's;.*href="\(.*key=[^"]*\)">.*;\1;p')"
	url="https://www.apkmirror.com$(req "$url" - | tr '\n' ' ' | sed -n 's;.*href="\(.*key=[^"]*\)">.*;\1;p')"
	req "$url" "$output"
}

# Downloading youtube
dl_yt() {
	echo "Downloading YouTube" | tee -a build.log
	local last_ver
	last_ver="$version"
	last_ver="${last_ver:-$(get_apk_vers "https://www.apkmirror.com/uploads/?appcategory=youtube" | get_largest_ver)}"

	echo "Choosing version '${last_ver}'" | tee -a build.log
	local base_apk="com.google.android.youtube.apk"
	declare -r dl_url=$(dl_apk "https://www.apkmirror.com/apk/google-inc/youtube/youtube-${last_ver//./-}-release/" \
		"APK</span>[^@]*@\([^#]*\)" \
		"$base_apk")
	echo "YouTube version: ${last_ver}" | tee -a build.log
	echo "downloaded from: [APKMirror - YouTube]($dl_url)" | tee -a build.log
	jq ".\"$apk\" = \"$last_ver\"" versions.json > versions.json.tmp && mv versions.json.tmp versions.json
}

# Architectures
ARM64_V8A="arm64-v8a"
ARM_V7A="arm-v7a"

# Downloading youtube music
dl_ytm() {
	local arch=$ARM64_V8A
	echo "Downloading YouTube Music (${arch})" | tee -a build.log
	local last_ver
	last_ver="$version"
	last_ver="${last_ver:-$(get_apk_vers "https://www.apkmirror.com/uploads/?appcategory=youtube-music" | get_largest_ver)}"

	echo "Choosing version '${last_ver}'" | tee -a build.log
	local base_apk="com.google.android.apps.youtube.music.apk"
	if [ "$arch" = "$ARM64_V8A" ]; then
		local regexp_arch='arm64-v8a</div>[^@]*@\([^"]*\)'
	elif [ "$arch" = "$ARM_V7A" ]; then
		local regexp_arch='armeabi-v7a</div>[^@]*@\([^"]*\)'
	fi
	declare -r dl_url=$(dl_apk "https://www.apkmirror.com/apk/google-inc/youtube-music/youtube-music-${last_ver//./-}-release/" \
		"$regexp_arch" \
		"$base_apk")
	echo "\nYouTube Music (${arch}) version: ${last_ver}" | tee -a build.log
	echo "downloaded from: [APKMirror - YouTube Music ${arch}]($dl_url)" | tee -a build.log
	jq ".\"$apk\" = \"$last_ver\"" versions.json > versions.json.tmp && mv versions.json.tmp versions.json
}

# Get into the build directory

if [ -z "$1" ]; then
    cd "$1"
else
    echo "Working directory not provided"
    exit -1
fi

## Main

for apk in "${!apks[@]}"; do
    if [ ! -f $apk ]; then
        echo "Downloading $apk" | tee -a build.log
		req "https://raw.githubusercontent.com/revanced/revanced-patches/main/patches.json" patches.json
		supported_vers="$(jq -r '.[].compatiblePackages[] | select(.name == "'$apk'") | .versions | last' patches.json)"
		version=0
		for vers in $supported_vers; do
			if [ $vers != "null" ]; then
				if [[ $version==0 || ${vers//[!0-9]/} -lt ${version//[!0-9]/} ]]; then
					version=$vers
				fi
			fi
		done
        version_present=$(jq -r ".\"$apk\"" versions.json)
        [[ ${version_present//[!0-9]/} -lt ${version//[!0-9]/} ]] && ${apks[$apk]} || echo "Recommended version of "$apk" already present" | tee -a build.log
    fi
done
