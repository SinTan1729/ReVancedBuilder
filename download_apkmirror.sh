#!/usr/bin/env bash

declare -A apks

apks["com.google.android.youtube"]=dl_yt
apks["com.google.android.apps.youtube.music"]=dl_ytm

flag=$2

# Read the settings
source "$1/build_settings"

## Functions

# Wget user agent
WGET_HEADER="User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"

# Wget function
req() { wget -nv -O "$2" --header="$WGET_HEADER" "$1"; }

# # Wget apk verions
# get_apk_vers() { req "$1" - | sed -n 's;.*Version:</span><span class="infoSlide-value">\(.*\) </span>.*;\1;p'; }

# # Wget apk verions(largest)
# get_largest_ver() {
# 	local max=0
# 	while read -r v || [ -n "$v" ]; do
# 		if [[ ${v//[!0-9]/} -gt ${max//[!0-9]/} ]]; then max=$v; fi
# 	done
# 	if [[ $max = 0 ]]; then echo ""; else echo "$max"; fi
# }

# Returns if $1 is less than $2
ver_less_than() {
	[[ ${1:0:1} == "v" ]] && var1=${1:1} || var1=$1
	[[ ${2:0:1} == "v" ]] && var2=${2:1} || var2=$2
	[[ $(echo $var1$'\n'$var2 | sort -V | tail -n1) != $var1 ]] && echo true || echo false
}

# Wget download apk
dl_apk() {
	local url=$1 regexp=$2 output=$3
	url="https://www.apkmirror.com$(req "$url" - | tr '\n' ' ' | sed -n "s/href=\"/@/g; s;.*${regexp}.*;\1;p")"
	echo "$url"
	url="https://www.apkmirror.com$(req "$url" - | tr '\n' ' ' | sed -n 's;.*href="\(.*key=[^"]*\)">.*;\1;p')"
	url="https://www.apkmirror.com$(req "$url" - | tr '\n' ' ' | sed -n 's;.*href="\(.*key=[^"]*\)">.*;\1;p')"
	req "$url" "$output"
}

# Downloading youtube
dl_yt() {
	if [[ $flag == checkonly ]]; then
		echo "[checkonly] YouTube has an update ($version_present -> $version)"
		return
	fi
	echo "Downloading YouTube"
	local last_ver
	last_ver="$version"
	# last_ver="${last_ver:-$(get_apk_vers "https://www.apkmirror.com/uploads/?appcategory=youtube" | get_largest_ver)}"

	echo "Choosing version '${last_ver}'"
	local base_apk="com.google.android.youtube.apk"
	declare -r dl_url=$(dl_apk "https://www.apkmirror.com/apk/google-inc/youtube/youtube-${last_ver//./-}-release/" \
		"APK</span>[^@]*@\([^#]*\)" \
		"$base_apk")
	echo "YouTube version: ${last_ver}"
	echo "downloaded from: [APKMirror - YouTube]($dl_url)"
	jq ".\"$apk\" = \"$last_ver\"" versions.json >versions.json.tmp && mv versions.json.tmp versions.json
}

# Architectures
ARM64_V8A="arm64-v8a"
ARM_V7A="arm-v7a"

# Downloading youtube music
dl_ytm() {
	if [[ $flag == checkonly ]]; then
		echo "[checkonly] YouTube Music has an update ($version_present -> $version)"
		return
	fi
	local arch=$ARM64_V8A
	echo "Downloading YouTube Music (${arch})"
	local last_ver
	last_ver="$version"
	# last_ver="${last_ver:-$(get_apk_vers "https://www.apkmirror.com/uploads/?appcategory=youtube-music" | get_largest_ver)}"

	echo "Choosing version '${last_ver}'"
	local base_apk="com.google.android.apps.youtube.music.apk"
	if [ "$arch" = "$ARM64_V8A" ]; then
		local regexp_arch='arm64-v8a</div>[^@]*@\([^"]*\)'
	elif [ "$arch" = "$ARM_V7A" ]; then
		local regexp_arch='armeabi-v7a</div>[^@]*@\([^"]*\)'
	fi
	declare -r dl_url=$(dl_apk "https://www.apkmirror.com/apk/google-inc/youtube-music/youtube-music-${last_ver//./-}-release/" \
		"$regexp_arch" \
		"$base_apk")
	echo "\nYouTube Music (${arch}) version: ${last_ver}"
	echo "downloaded from: [APKMirror - YouTube Music ${arch}]($dl_url)"
	jq ".\"$apk\" = \"$last_ver\"" versions.json >versions.json.tmp && mv versions.json.tmp versions.json
}

# Get into the build directory

if [ -d "$1" ]; then
	cd "$1"
else
	echo "Working directory not provided"
	exit -1
fi

## Main
try=0
while :; do
	try=$(($try + 1))
	[ $try -gt 10 ] && echo "API error!" && exit 3
	curl -X 'GET' 'https://releases.revanced.app/patches' -H 'accept: application/json' -o patches.json
	cat patches.json | jq -e '.error' >/dev/null 2>&1 || break
	echo "API failure, trying again. $((10 - $try)) tries left..."
	sleep 10
done

for apk in "${!apks[@]}"; do
	# Skip if app not specified for build
	[[ "$apk" == "com.google.android.youtube" && "$YT_NONROOT" == false && "$YT_ROOT" == false ]] && continue
	[[ "$apk" == "com.google.android.apps.youtube.music" && "$YTM_NONROOT" == false && "$YTM_ROOT" == false ]] && continue

	echo "Checking $apk"
	supported_vers="$(jq -r '.[].compatiblePackages[] | select(.name == "'$apk'") | .versions | last' patches.json)"
	version=0
	for vers in $supported_vers; do
		[ $vers != "null" ] && [[ $(ver_less_than $vers $version) == true || $version == 0 ]] && version=$vers
	done
	version_present=$(jq -r ".\"$apk\"" versions.json)
	[ -z "$version_present" ] && version_present=0
	[[ $(ver_less_than $version_present $version) == true || ! -f $apk.apk || $2 == force ]] && ${apks[$apk]} || echo "Recommended version ($version_present) of "$apk" is already present"
done
