# Privacy and public-release rules

soloPAW is intended to be safe to show on livestreams and safe to publish as source code.

## Do not publish

- personal home paths such as `/home/<username>/...`;
- hostnames or device serial numbers unless intentionally public;
- GitHub tokens, passwords, API keys, `.env` files, SSH private keys, browser profiles, or credential stores;
- raw Input Remapper debug/journal dumps unless reviewed and sanitized;
- unrelated `~/.config`, `.gitconfig`, shell history, Steam data, or system logs;
- private screenshots that expose directories, notifications, accounts, or browser data.

The public Input Remapper JSON files omit `origin_hash` and personal filesystem data. They are reference profiles, not exact hardware guarantees.

The Profile Switcher resolves standard user locations at runtime and can hide real profile filenames behind Common Names. File-manager/file-picker actions are explicitly marked for off-stream use.
