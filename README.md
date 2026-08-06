English | [简体中文](README.zh-CN.md)

# Apache Guacamole 1.6.0 Input Recovery Fix v7

This repository contains an unofficial downstream patch candidate for **Apache Guacamole 1.6.0**. It addresses two input failures that may occur after switching browser tabs or leaving a Guacamole session in the background for a long time:

1. In Guacamole's Text input mode, composed Chinese text may remain in the lower-left input field, fail to reach the remote application, or cause Backspace/Delete to stop working.
2. When Guacamole's input method is set to None, the remote Windows Microsoft Pinyin IME or regular keyboard input may stop working after returning to the tab.

> Use only the image tag `trilogys/guacamole:1.6.0`.

## Supported modes

### Mode A: local IME with Guacamole Text input

```text
Remote Windows language: ENG
Guacamole input method: Text input
Local input method: Chinese IME
```

The patch:

- recovers from a missing browser `compositionend` event;
- handles different `input` and `compositionend` event orders;
- restores keyboard focus to the active remote connection;
- restores text, Backspace, and Delete delivery;
- prevents the hidden raw-keyboard `InputSink` from stealing focus from the visible lower-left text field.

### Mode B: Microsoft Pinyin inside remote Windows

```text
Guacamole input method: None
Local input language: ENG or a local IME
Remote Windows input method: Microsoft Pinyin
RDP keyboard layout: en-us-qwerty
```

The patch:

- makes the remote input language authoritative by preventing the hidden raw-keyboard input sink from accepting local IME composition text;
- resets Guacamole's recorded key state when the tab becomes hidden;
- restores keyboard focus to the active remote connection when the tab returns;
- refocuses the hidden raw-keyboard input sink;
- explicitly releases AltGr, Shift, Ctrl, Alt, Meta, Windows/Super, and Hyper;
- coalesces repeated `focus` and `visibilitychange` events within a short interval;
- handles long background suspension and the `freeze`, `resume`, and `pageshow` lifecycle events;
- synchronously rebuilds Chromium's native input context on the first pointer, mouse, touch, click, or keyboard gesture after returning;
- keeps `Ctrl+Alt+Shift` as an independent recovery path while preserving the side-menu toggle behavior;
- provides `Ctrl+Alt+K` and the Recover keyboard capture menu action as manual recovery paths;
- avoids stealing focus from Guacamole login fields, settings, buttons, links, and editable controls.

## Build requirements

The server requires:

```text
Docker
curl
patch
Python 3
tar
sha256sum
mktemp
```

Node.js is optional. When available, it is used for additional JavaScript syntax checks on modified files.

## Build

```bash
sudo apt-get update
sudo apt-get install -y curl patch python3

tar -xzf guacamole-ime-fix-v7-1.6.0.tar.gz
cd guacamole-ime-fix-v7
sha256sum -c ../guacamole-ime-fix-v7-1.6.0.tar.gz.sha256
./build.sh
```

Default image:

```text
trilogys/guacamole:1.6.0
```

`build.sh` performs the following steps:

1. verifies every file in the patch package;
2. locks the Guacamole version to 1.6.0;
3. runs scope, mode-isolation, race-condition, and state-regression checks;
4. downloads the official Apache source archive and verifies its SHA-256;
5. runs `patch --dry-run` against the real source tree;
6. applies the patch and verifies the modified source files;
7. builds with the official Dockerfile and runs the upstream Maven/frontend tests by default;
8. inspects the image and runs an `initdb` smoke test;
9. prints the image ID and patch SHA-256.

If resources are temporarily constrained, upstream tests can be skipped for troubleshooting only:

```bash
MAVEN_ARGUMENTS=-DskipTests=true ./build.sh
```

Use the default build settings for deployment.

### Optional build parameters

```bash
IMAGE_NAME=trilogys/guacamole:1.6.0 ./build.sh
WORK_DIR=/var/tmp ./build.sh
KEEP_WORK_DIR=true ./build.sh
PULL_BASE_IMAGES=true ./build.sh
```

`WORK_DIR` is only the parent directory for temporary files. The script creates a separate random subdirectory within it and never directly deletes the user-provided directory.

The build does not force `--pull` by default, which prevents the base image from changing unintentionally on every rebuild. The first build may still fetch images referenced by the official Dockerfile, so fully bit-for-bit reproducible builds require those base images to be pinned locally.

## Server deployment workflow

The Git checkout is used only to build the image. The existing Compose project
remains responsible for running Guacamole and its database-related services:

```text
Source and build: /opt/Guacamole/guacamole/guacamole-repo
Compose runtime:  /opt/Guacamole/guacamole
```

Do not stop the currently running Guacamole container before the build. It will
continue using its existing image ID until the replacement container is created.

### 1. Update the server checkout

```bash
cd /opt/Guacamole/guacamole/guacamole-repo

git status --short
git fetch origin dev
git switch dev
git pull --ff-only origin dev
git log --oneline -5
```

Stop if `git status --short` prints any local changes. Confirm that the remote
IME fix commit is contained in the checked-out history:

```bash
git merge-base --is-ancestor f5a5d37 HEAD
git show --no-patch --oneline f5a5d37
```

### 2. Preserve the current image for rollback

```bash
docker tag \
  trilogys/guacamole:1.6.0 \
  trilogys/guacamole:1.6.0-before-remote-ime
```

### 3. Build the replacement image

The controlled test deployment may skip the time-consuming upstream Maven test
suite. Package integrity, patch structure, regression checks, patch dry-run,
source verification, image inspection, and the `initdb` smoke test still run:

```bash
cd /opt/Guacamole/guacamole/guacamole-repo

MAVEN_ARGUMENTS=-DskipTests=true \
IMAGE_NAME=trilogys/guacamole:1.6.0 \
bash ./build.sh
```

Verify that the resulting image contains the expected patch:

```bash
docker image inspect trilogys/guacamole:1.6.0 \
  --format '{{index .Config.Labels "io.guacamole.inputfix.patch-sha256"}}'
```

Expected value:

```text
28b7224360f9bbd56933e465feff55a6df146c06d5e7ef91e8ffbebd5b9f2e7c
```

### 4. Recreate only the Guacamole web container

```bash
cd /opt/Guacamole/guacamole

docker compose config
docker compose up -d --force-recreate guacamole
docker compose ps
docker compose logs --tail=100 guacamole
```

This does not migrate or replace PostgreSQL data, guacd, Nginx, FRP,
connection accounts, recordings, or shared directories. Do not run
`docker compose down -v` or delete database volumes.

`docker-compose.override.yml` selects `trilogys/guacamole:1.6.0` by default.
The official Apache Guacamole 1.6.0 image remains available through
`docker-compose.official.yml` as a separate fallback.

This patch does not modify:

```text
guacd
PostgreSQL schema or data
Nginx
FRP
Connection accounts
Recording or shared directories
```

Perform one hard refresh after opening the new image for the first time:

```text
Ctrl + F5
```

## Required acceptance testing

See `TEST_MATRIX.md` for the detailed procedure. At minimum, verify:

- with the local IME set to Chinese and remote Windows set to ENG, letters remain English;
- with the local IME left in Chinese and remote Microsoft Pinyin enabled, candidate selection is handled by the remote IME;
- 20 tab switches in each input mode in Chrome and Edge;
- no stuck remote modifier after switching away while holding Ctrl, Shift, or Alt;
- Chinese candidate selection, numeric candidate selection, Backspace, Delete, arrow keys, and Enter;
- Guacamole menus, login fields, and settings retain correct focus behavior;
- input still works after disconnecting and reconnecting the same account;
- rollback to the official image succeeds.

## Known limitations

- Shortcuts such as `Win+Space` and `Alt+Tab` may be intercepted by the local operating system or browser. Use the remote Windows taskbar language selector when necessary.
- End-to-end validation against your actual Windows RDP session is still required.
- iframe deployments, mobile WebViews, multiple simultaneously selected connections, and browsers other than Chrome/Edge require separate validation.
- The package does not include a prebuilt image, image signature, SBOM, or vulnerability scan results.

## Rollback

```bash
docker tag \
  trilogys/guacamole:1.6.0-before-remote-ime \
  trilogys/guacamole:1.6.0

cd /opt/Guacamole/guacamole
docker compose up -d --force-recreate guacamole
```

The previous custom image can therefore be restored without rebuilding. The
official image remains a secondary fallback:

```bash
cd /opt/Guacamole/guacamole
docker compose -f docker-compose.yml -f docker-compose.official.yml \
  up -d --force-recreate guacamole
```

No database restore is required because the patch introduces no database migration.

## License

This patch package is licensed under the Apache License 2.0. Apache Guacamole copyright and NOTICE requirements remain unchanged. This package is not an official Apache Software Foundation release.
