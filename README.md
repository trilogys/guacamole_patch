English | [简体中文](README.zh-CN.md)

# guacamole_patch

An unofficial downstream patch for **Apache Guacamole 1.6.0** that improves keyboard and IME recovery after browser tab switching, background suspension, and page lifecycle changes.

This repository is not an official Apache Software Foundation release.

## Quick deployment

Pull the published image:

```bash
docker pull ghcr.io/trilogys/guacamole_patch:1.6.0
```

Use it in Docker Compose:

```yaml
services:
  guacamole:
    image: ghcr.io/trilogys/guacamole_patch:1.6.0
```

Update only the Guacamole web container:

```bash
docker compose pull guacamole
docker compose up -d --force-recreate --no-deps guacamole
docker compose ps
docker compose logs --tail=100 guacamole
```

Docker reuses unchanged layers, so later pulls normally download only changed layers. Do not run `docker compose down -v` or delete database volumes.

## Published image tags

- `1.6.0`: current release image; this tag is updated on each release build.
- `main`: latest image built from the `main` branch.
- `sha-<commit>`: immutable tag for a specific source commit.
- `dev`: development image built from the `dev` branch.

For production builds, run the workflow from `main`. Running it from `dev` also updates the shared `1.6.0` tag.

## What the patch addresses

### Guacamole Text input with a local IME

```text
Remote Windows language: ENG
Guacamole input method: Text input
Local input method: Chinese IME
```

The patch recovers missing composition events, restores focus to the active connection, restores text/Backspace/Delete delivery, and prevents the hidden raw-keyboard input sink from stealing focus from the visible text field.

### Microsoft Pinyin inside remote Windows

```text
Guacamole input method: None
Local input language: ENG or a local IME
Remote Windows input method: Microsoft Pinyin
RDP keyboard layout: en-us-qwerty
```

The patch resets recorded key state when the page is hidden, restores keyboard capture after returning, releases stuck modifiers, handles long background suspension and page lifecycle events, and rebuilds Chromium's native input context on the first user gesture.

Manual recovery remains available through `Ctrl+Alt+K` and the **Recover keyboard capture** menu action.

## GitHub Actions build

Open **Actions → Build and publish Guacamole image → Run workflow**, select `main`, and run the workflow.

A successful build publishes:

```text
ghcr.io/trilogys/guacamole_patch:1.6.0
ghcr.io/trilogys/guacamole_patch:main
ghcr.io/trilogys/guacamole_patch:sha-<commit>
```

## Manual build

Requirements:

```text
Docker
curl
patch
Python 3
tar
sha256sum
mktemp
```

Clone and build:

```bash
git clone https://github.com/trilogys/guacamole_patch.git
cd guacamole_patch

IMAGE_NAME="ghcr.io/trilogys/guacamole_patch:1.6.0" \
bash ./build.sh
```

For a faster troubleshooting build:

```bash
MAVEN_ARGUMENTS="-T 1C -Dmaven.test.skip=true" \
IMAGE_NAME="ghcr.io/trilogys/guacamole_patch:1.6.0" \
bash ./build.sh
```

`build.sh` verifies the patch package and Apache source archive, runs regression checks, dry-runs and applies the patch, builds the official Dockerfile, inspects the image, and runs an `initdb` smoke test.

## Verify the image

```bash
docker image inspect ghcr.io/trilogys/guacamole_patch:1.6.0 \
  --format '{{index .Config.Labels "io.guacamole.inputfix.patch-sha256"}}'
```

Expected patch SHA-256:

```text
28b7224360f9bbd56933e465feff55a6df146c06d5e7ef91e8ffbebd5b9f2e7c
```

## Acceptance testing

See [TEST_MATRIX.md](TEST_MATRIX.md) for the complete procedure. At minimum, verify:

- local Chinese IME with remote Windows set to ENG;
- remote Microsoft Pinyin candidate selection;
- repeated tab switching in Chrome and Edge;
- no stuck Ctrl, Shift, or Alt keys;
- Backspace, Delete, arrow keys, Enter, and numeric candidate selection;
- reconnecting the same account;
- rollback to a known working image.

## Scope and limitations

The patch does not modify `guacd`, PostgreSQL schema or data, Nginx, FRP, connection accounts, recordings, or shared directories.

Shortcuts such as `Win+Space` and `Alt+Tab` may be intercepted by the local operating system or browser. Validate the image against the actual Windows RDP environment before production rollout.

## License

This patch package is licensed under the Apache License 2.0. Apache Guacamole copyright and NOTICE requirements remain unchanged.
