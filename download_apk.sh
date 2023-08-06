#!/usr/bin/env bash

declare -A apks

apks["com.google.android.youtube"]=dl_yt
apks["com.google.android.apps.youtube.music"]=dl_ytm

flag=$2

# Read the settings
source "$1/build_settings"

## Functions

# Wget user agent
WGET_HEADER="User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"

# Wget function
req() { wget -nv -4 -O "$2" --header="$WGET_HEADER" "$1"; }

# Returns true if $1 is less than $2
ver_less_than() {
	[[ ${1:0:1} == "v" ]] && var1=${1:1} || var1=$1
	[[ ${2:0:1} == "v" ]] && var2=${2:1} || var2=$2
	[[ $(echo $var1$'\n'$var2 | sort -V | tail -n1) != $var1 ]] && echo true || echo false
}

# APKPure Download function
dl_apkpure() {
	version="$1"
	app="$2"
	apkpure_appname="$3"
	$hard_vers && best_match="$version" || best_match="$(apkpure_best_match $version $app $apkpure_appname)"

	# if [[ "$version" == "$best_match" || "$version" == "latest" ]]; then
	# 	echo "Downloading version $best_match from APKPure"
	# else
	# 	echo "Unable to get version $version, downloading version $best_match instead"
	# fi

	vers_code="$(req https://apkpure.com/$apkpure_appname/$app/versions - | htmlq --attribute data-dt-versioncode 'a[data-dt-version="'$version'"][data-dt-apkid^="b\/APK\/"]')"
	url="https://d.apkpure.com/b/APK/$app?versionCode=$vers_code"

	req "$url" "$app.apk"
	echo "$url"
}

# Get the best match even if the desired version isn't there
# OUtputs the latest version with supplied version 0
apkpure_best_match() {
	version="$1"
	app="$2"
	apkpure_appname="$3"

	vers_list=$(req https://apkpure.com/$apkpure_appname/$app/versions - | htmlq --attribute data-dt-version 'a[data-dt-apkid^="b\/APK\/"]')
	if [[ "$version" == "latest" ]]; then
		match="$(echo "$vers_list" | head -1)"
	elif $(echo "$vers_list" | grep -q "$version"); then
		match="$version"
	else
		match="$(echo "$vers_list"$'\n'"$version" | sort -V | grep -B 1 "$version" | head -1)"
	fi

	echo "$match"
}

# Downloading youtube
dl_yt() {
	appname=com.google.android.youtube
	$hard_vers || version="$(apkpure_best_match "$version" $appname youtube)"
	if [[ ! $(ver_less_than "$version_present" "$version") && -f $appname.apk ]]; then
		echo "Version $version is already present"
		return
	fi

	if [[ $flag == checkonly ]]; then
		echo "[checkonly] YouTube has an update ($version_present -> $version)"
		return
	fi
	echo "Downloading YouTube"

	echo "Choosing version $version"
	declare -r dl_url=$(dl_apkpure "$version" $appname youtube)
	echo "YouTube version: $version"
	echo "downloaded from: [APKMirror - YouTube]($dl_url)"
	jq ".\"$apk\" = \"$version\"" versions.json >versions.json.tmp && mv versions.json.tmp versions.json
}

# Downloading youtube music
dl_ytm() {
	appname=com.google.android.apps.youtube.music
	$hard_vers || version="$(apkpure_best_match "$version" $appname youtube-music)"
	if [[ ! $(ver_less_than "$version_present" "$version") && -f $appname.apk ]]; then
		echo "Version $version is already present"
		return
	fi

	if [[ $flag == checkonly ]]; then
		echo "[checkonly] YouTube Music has an update ($version_present -> $version)"
		return
	fi
	echo "Downloading YouTube Music"

	echo "Choosing version '${version}'"
	# declare -r dl_url=$(dl_apkpure "$version" $appname youtube-music)
	dl_apkpure "$version" $appname youtube-music
	echo "YouTube Music version: $version"
	echo "downloaded from: [APKMirror - YouTube Music]($dl_url)"
	jq ".\"$apk\" = \"$version\"" versions.json >versions.json.tmp && mv versions.json.tmp versions.json
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
	if [[ "$apk" == "com.google.android.youtube" && "$YT_VERSION" != "" ]]; then
		version="$YT_VERSION"
		echo "Using version $version for $apk given in build_settings"
		hard_vers=true
	elif [[ "$apk" == "com.google.android.apps.youtube.music" && "$YTM_VERSION" != "" ]]; then
		version="$YTM_VERSION"
		echo "Using version $version for $apk given in build_settings"
		hard_vers=true
	else
		echo "Figuring out best version for $apk"
		supported_vers="$(jq -r '.[].compatiblePackages[] | select(.name == "'$apk'") | .versions | last' patches.json)"
		version=0
		for vers in $supported_vers; do
			[ $vers != "null" ] && [[ $(ver_less_than $vers $version) == true || $version == 0 ]] && version=$vers
		done
		hard_vers=false
	fi

	version_present=$(jq -r ".\"$apk\"" versions.json)
	[[ -z "$version_present" || "$version" == "null" ]] && version_present=0
	[[ "$version" == "0" ]] && version=latest

	[[ "$version_present" != "$version" || ! -f $apk.apk || $2 == force ]] && ${apks[$apk]} || echo "Recommended version ($version_present) of "$apk" is already present"
done
