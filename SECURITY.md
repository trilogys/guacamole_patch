# Security notes

- This patch does not change authentication, authorization, database schemas, clipboard handling, file transfer, RDP encryption, or FRP configuration.
- Build only from the included script after verifying the outer archive checksum.
- Keep the generated image in a private/local registry unless you intentionally publish it.
- Do not push the image under the official `guacamole/guacamole` namespace.
- Scan the generated image with your preferred scanner before Internet-facing deployment.
- Record the image ID and patch SHA-256 printed by `build.sh` for rollback and incident response.
- The base images and apt packages used by the upstream Dockerfile are not pinned by digest; rebuilds may differ.
