# based on https://github.com/kivy/python-for-android/blob/master/Dockerfile

FROM ubuntu:20.04@sha256:86ac87f73641c920fb42cc9612d4fb57b5626b56ea2a19b894d0673fd5b4f2e9

ENV DEBIAN_FRONTEND=noninteractive

ENV ANDROID_HOME="/opt/android"

# configure locale
RUN apt update -qq > /dev/null && apt install -qq --yes --no-install-recommends \
    locales && \
    locale-gen en_US.UTF-8
ENV LANG="en_US.UTF-8" \
    LANGUAGE="en_US.UTF-8" \
    LC_ALL="en_US.UTF-8"

RUN apt -y update -qq \
    && apt -y install -qq --no-install-recommends curl unzip ca-certificates \
    && apt -y autoremove


ENV ANDROID_NDK_HOME="${ANDROID_HOME}/android-ndk"
ENV ANDROID_NDK_VERSION="22b"
ENV ANDROID_NDK_HASH="ac3a0421e76f71dd330d0cd55f9d99b9ac864c4c034fc67e0d671d022d4e806b"
ENV ANDROID_NDK_HOME_V="${ANDROID_NDK_HOME}-r${ANDROID_NDK_VERSION}"

# get the latest version from https://developer.android.com/ndk/downloads/index.html
ENV ANDROID_NDK_ARCHIVE="android-ndk-r${ANDROID_NDK_VERSION}-linux-x86_64.zip"
ENV ANDROID_NDK_DL_URL="https://dl.google.com/android/repository/${ANDROID_NDK_ARCHIVE}"

# download and install Android NDK
RUN curl --location --progress-bar \
        "${ANDROID_NDK_DL_URL}" \
        --output "${ANDROID_NDK_ARCHIVE}" \
    && echo "${ANDROID_NDK_HASH} ${ANDROID_NDK_ARCHIVE}" | sha256sum -c - \
    && mkdir --parents "${ANDROID_NDK_HOME_V}" \
    && unzip -q "${ANDROID_NDK_ARCHIVE}" -d "${ANDROID_HOME}" \
    && ln -sfn "${ANDROID_NDK_HOME_V}" "${ANDROID_NDK_HOME}" \
    && rm -rf "${ANDROID_NDK_ARCHIVE}"


ENV ANDROID_SDK_HOME="${ANDROID_HOME}/android-sdk"

# get the latest version from https://developer.android.com/studio/index.html
ENV ANDROID_SDK_TOOLS_VERSION="8092744"
ENV ANDROID_SDK_BUILD_TOOLS_VERSION="30.0.3"
ENV ANDROID_SDK_HASH="d71f75333d79c9c6ef5c39d3456c6c58c613de30e6a751ea0dbd433e8f8b9cbf"
ENV ANDROID_SDK_TOOLS_ARCHIVE="commandlinetools-linux-${ANDROID_SDK_TOOLS_VERSION}_latest.zip"
ENV ANDROID_SDK_TOOLS_DL_URL="https://dl.google.com/android/repository/${ANDROID_SDK_TOOLS_ARCHIVE}"
ENV ANDROID_SDK_MANAGER="${ANDROID_SDK_HOME}/tools/bin/sdkmanager --sdk_root=${ANDROID_SDK_HOME}"

# download and install Android SDK
RUN curl --location --progress-bar \
        "${ANDROID_SDK_TOOLS_DL_URL}" \
        --output "${ANDROID_SDK_TOOLS_ARCHIVE}" \
    && echo "${ANDROID_SDK_HASH} ${ANDROID_SDK_TOOLS_ARCHIVE}" | sha256sum -c - \
    && mkdir --parents "${ANDROID_SDK_HOME}" \
    && unzip -q "${ANDROID_SDK_TOOLS_ARCHIVE}" -d "${ANDROID_SDK_HOME}" \
    && mv "${ANDROID_SDK_HOME}/cmdline-tools" "${ANDROID_SDK_HOME}/tools" \
    && rm -rf "${ANDROID_SDK_TOOLS_ARCHIVE}"

# update Android SDK, install Android API, Build Tools...
RUN mkdir --parents "${ANDROID_SDK_HOME}/.android/" \
    && echo '### User Sources for Android SDK Manager' \
        > "${ANDROID_SDK_HOME}/.android/repositories.cfg"

# accept Android licenses (JDK necessary!)
RUN apt -y update -qq \
    && apt -y install -qq --no-install-recommends \
        openjdk-11-jdk-headless \
    && apt -y autoremove
RUN yes | ${ANDROID_SDK_MANAGER} --licenses > /dev/null

# download platforms, API, build tools
RUN ${ANDROID_SDK_MANAGER} "platforms;android-30" > /dev/null && \
    ${ANDROID_SDK_MANAGER} "build-tools;${ANDROID_SDK_BUILD_TOOLS_VERSION}" > /dev/null && \
    ${ANDROID_SDK_MANAGER} "extras;android;m2repository" > /dev/null && \
    chmod +x "${ANDROID_SDK_HOME}/tools/bin/avdmanager"

# download ANT
ENV APACHE_ANT_VERSION="1.9.4"
ENV APACHE_ANT_HASH="66d3edcbb0eba11387705cd89178ffb65e55cd53f13ca35c1bb983c0f9992540"
ENV APACHE_ANT_ARCHIVE="apache-ant-${APACHE_ANT_VERSION}-bin.tar.gz"
ENV APACHE_ANT_DL_URL="https://archive.apache.org/dist/ant/binaries/${APACHE_ANT_ARCHIVE}"
ENV APACHE_ANT_HOME="${ANDROID_HOME}/apache-ant"
ENV APACHE_ANT_HOME_V="${APACHE_ANT_HOME}-${APACHE_ANT_VERSION}"

RUN curl --location --progress-bar \
        "${APACHE_ANT_DL_URL}" \
        --output "${APACHE_ANT_ARCHIVE}" \
    && echo "${APACHE_ANT_HASH} ${APACHE_ANT_ARCHIVE}" | sha256sum -c - \
    && tar -xf "${APACHE_ANT_ARCHIVE}" -C "${ANDROID_HOME}" \
    && ln -sfn "${APACHE_ANT_HOME_V}" "${APACHE_ANT_HOME}" \
    && rm -rf "${APACHE_ANT_ARCHIVE}"


# install system/build dependencies
# https://github.com/kivy/buildozer/blob/master/docs/source/installation.rst#android-on-ubuntu-2004-64bit
# TODO probably need to pin versions of at least some of these for over-time reproducibility?
RUN apt -y update -qq \
    && apt -y install -qq --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-venv \
        wget \
        lbzip2 \
        patch \
        sudo \
        software-properties-common \
        git \
        zip \
        unzip \
        build-essential \
        ccache \
        autoconf \
        libtool \
        pkg-config \
        zlib1g-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libtinfo5 \
        cmake \
        libffi-dev \
        libssl-dev \
        automake \
        gettext \
        libltdl-dev \
    && apt -y autoremove \
    && apt -y clean


# create new user to avoid using root; but with sudo access and no password for convenience.
ENV USER="user"
ENV HOME_DIR="/home/${USER}"
ENV WORK_DIR="${HOME_DIR}/wspace" \
    PATH="${HOME_DIR}/.local/bin:${PATH}"
RUN useradd --create-home --shell /bin/bash ${USER}
RUN usermod -append --groups sudo ${USER}
RUN echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
WORKDIR ${WORK_DIR}
RUN chown --recursive ${USER} ${WORK_DIR} ${ANDROID_SDK_HOME}
RUN chown ${USER} /opt
USER ${USER}


COPY contrib/deterministic-build/requirements-build-base.txt /opt/deterministic-build/
COPY contrib/deterministic-build/requirements-build-android.txt /opt/deterministic-build/
RUN python3 -m pip install --no-build-isolation --no-dependencies --user \
    -r /opt/deterministic-build/requirements-build-base.txt
RUN python3 -m pip install --no-build-isolation --no-dependencies --user \
    -r /opt/deterministic-build/requirements-build-android.txt

# install buildozer
RUN cd /opt \
    && git clone https://github.com/kivy/buildozer \
    && cd buildozer \
    && git remote add sombernight https://github.com/SomberNight/buildozer \
    && git fetch --all \
    # commit: from branch sombernight/electrum_20210421
    && git checkout "d570116e88184b0eca0c6b59a25edd49d977da23^{commit}" \
    && python3 -m pip install --no-build-isolation --no-dependencies --user -e .

# install python-for-android
RUN cd /opt \
    && git clone https://github.com/kivy/python-for-android \
    && cd python-for-android \
    && git remote add sombernight https://github.com/SomberNight/python-for-android \
    && git remote add accumulator https://github.com/accumulator/python-for-android \
    && git fetch --all \
    # commit: from branch accumulator/qt5-wip
    && git checkout "ebbe8dcc271e36468666feb98f936d0a96936cf2^{commit}" \
    && python3 -m pip install --no-build-isolation --no-dependencies --user -e .

# build env vars
ENV USE_SDK_WRAPPER=1
ENV GRADLE_OPTS="-Xmx1536M -Dorg.gradle.jvmargs='-Xmx1536M'"
