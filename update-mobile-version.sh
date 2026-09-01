#!/bin/bash
# This script is used to generate new version for nmis-mobile

CURRENT_VERSION=$(cat ./app/package.json | grep version | awk -F\" '{print $4}')
CURRENT_BRANCH=$(git branch --show-current)

if [[ "$CURRENT_BRANCH" != "main" ]]; then
    printf "Current Branch: %s\n" "${CURRENT_BRANCH}"
    printf "Please checkout to main branch\n"
    exit 0
else
    git pull
fi

MAJOR=$(echo "${CURRENT_VERSION}" | awk -F. '{print $1}')
MINOR=$(echo "${CURRENT_VERSION}" | awk -F. '{print $2}')
PATCH=$(echo "${CURRENT_VERSION}" | awk -F. '{print $3}')

printf "Current Version: %s\n" "${CURRENT_VERSION}"
read -r -p "Do you want to release new version? [y/N] " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])+$ ]]; then
    read -r -p "Please select release type [major/minor/patch] " response
    # GENERATE NEW VERSION
    if [[ "$response" == "major" ]]; then
        NEW_VERSION=$(echo "${CURRENT_VERSION}" | awk -F. '{$1 = $1 + 1; $2=0; $3=0;} 1' OFS=.)
    elif [[ "$response" == "minor" ]]; then
        NEW_VERSION="${MAJOR}.$((MINOR + 1)).0"
    elif [[ "$response" == "patch" ]]; then
        NEW_VERSION="${MAJOR}.${MINOR}.$((PATCH + 1))"
    else
        printf "Aborted\n"
        exit 0
    fi

    NEW_MAJOR=$(echo "${NEW_VERSION}" | awk -F. '{print $1}')
    NEW_MINOR=$(echo "${NEW_VERSION}" | awk -F. '{print $2}')
    NEW_PATCH=$(echo "${NEW_VERSION}" | awk -F. '{print $3}')

    # Each component gets a fixed width: MAJOR | MINOR | PATCH padded to 2 digits,
    # so 4.2.1 -> 4201, matching every code published so far. Simply removing the
    # dots (4.1.30 -> 4130) only worked while the widths happened to line up: 4.2.0
    # collapsed to 420, BELOW the 4130 already on Play, and Play Store rejects a
    # version code that does not increase.
    #
    # The scheme holds while minor stays single-digit. At 4.10.0 it would produce
    # 5000 and collide with 5.0.0, so it stops rather than generating a code that
    # cannot be published.
    if [[ "${NEW_MINOR}" -gt 9 ]]; then
        printf "Minor version %s needs more than one digit.\n" "${NEW_MINOR}"
        printf "The version code scheme (MAJOR|MINOR|PATCH) is exhausted and would\n"
        printf "collide with major %s. Widen it before releasing %s.\n" \
            "$((NEW_MAJOR + 1))" "${NEW_VERSION}"
        exit 1
    fi
    if [[ "${NEW_PATCH}" -gt 99 ]]; then
        printf "Patch %s does not fit in two digits. Release a minor instead.\n" "${NEW_PATCH}"
        exit 1
    fi
    NEW_VERSION_INT=$((NEW_MAJOR * 1000 + NEW_MINOR * 100 + NEW_PATCH))

    # A rebuild of an unchanged version is published by bumping the code by hand, so
    # the code on disk can already be ahead of what the version implies. Never go
    # backwards, and never reuse a code that has been built.
    CURRENT_VERSION_INT=$(grep '"versionCode"' app/app.json | grep -o '[0-9]\+')
    if [[ -n "${CURRENT_VERSION_INT}" && "${NEW_VERSION_INT}" -le "${CURRENT_VERSION_INT}" ]]; then
        printf "Version code %s would not increase on %s, using %s instead.\n" \
            "${NEW_VERSION_INT}" "${CURRENT_VERSION_INT}" "$((CURRENT_VERSION_INT + 1))"
        NEW_VERSION_INT=$((CURRENT_VERSION_INT + 1))
    fi

    # UPDATE VERSION IN /app/package.json
    sed -i.bak "s/\"version\": *\"[^\"]*\"/\"version\": \"${NEW_VERSION}\"/" app/package.json
    rm app/package.json.bak

    # UPDATE VERSION IN /app/src/build.json
    sed -i.bak "s/\"appVersion\": *\"[^\"]*\"/\"appVersion\": \"${NEW_VERSION}\"/" app/src/build.json
    rm app/src/build.json.bak

    # UPDATE VERSION IN /app/app.json
    sed -i.bak "s/\"version\": *\"[^\"]*\"/\"version\": \"${NEW_VERSION}\"/" app/app.json
    # UPDATE ANDROID VERSION CODE IN /app/app.json
    sed -i.bak "s/\"versionCode\": *[^\"]*/\"versionCode\": $NEW_VERSION_INT/" app/app.json
    rm app/app.json.bak

    printf "Updated to version: %s (versionCode %s)\n" "${NEW_VERSION}" "${NEW_VERSION_INT}"
    exit 0
else
    printf "Aborted\n"
    exit 0
fi
