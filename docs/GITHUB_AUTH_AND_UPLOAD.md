# GitHub authentication and first upload

## Recommended: GitHub CLI browser authentication

You normally do **not** need to manually create or paste a personal access token.

On Arch/CachyOS:

```bash
sudo pacman -S --needed git github-cli
```

Authenticate:

```bash
gh auth login --web --git-protocol https
gh auth status
```

GitHub CLI uses the browser/device flow and stores the resulting credential using the system credential store when available.

Never paste a GitHub token into a README, shell script, Git commit, issue, livestream, or support conversation.

## Optional: fine-grained personal access token

If you specifically need a manual token:

1. GitHub → Settings.
2. Developer settings.
3. Personal access tokens.
4. Fine-grained tokens.
5. Generate a new token.
6. Choose an expiration date.
7. Limit repository access to soloPAW when possible.
8. Grant only the repository permission needed to push code (normally **Contents: Read and write** for this use case).

Treat it like a password. Do not embed it in a remote URL.

## First local commit

```bash
git init -b main
git add .
git status
git commit -m "Initial soloPAW public release"
```

Review `git status` before committing.

## Create and push with GitHub CLI

```bash
gh repo create soloPAW --public --source=. --remote=origin --push
```

If an empty repository already exists on GitHub:

```bash
git remote add origin https://github.com/YOUR-GITHUB-NAME/soloPAW.git
git remote -v
git push -u origin main
```

## Before the first public push

```bash
./scripts/doctor.sh
git status --short
git diff --cached --stat
```

The package intentionally does not select a software license on your behalf. See `LICENSE_OPTIONS.md`.

Official references:
- https://cli.github.com/manual/gh_auth_login
- https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
