# How this folder is wired to GitHub

## Current state

```
remote   https://github.com/TCLWNC/TypeBridge.git   (private)
local    C:\Users\Administrator\Documents\Codex\2026-09-26\new-chat\outputs\CrossLink
origin   main  (tracking origin/main)
auth     stored in Windows Credential Manager, so pushes do not ask again
```

## Pushing changes

```powershell
cd C:\Users\Administrator\Documents\Codex\2026-09-26\new-chat\outputs\CrossLink
git add -A
git commit -m "what changed"
git push
```

That is all — the credential is already stored.

## If authentication stops working

Generate a new token (GitHub → Settings → Developer settings → Personal access tokens →
Tokens (classic) → Generate new token, scope `repo`), then store it once:

```powershell
git credential approve      # then paste protocol/host/username/password lines
```

or simply run `git push` and let the credential manager open its sign-in window.

## If you move the project to another remote

```powershell
git remote set-url origin https://github.com/your-name/your-repo.git
git push -u origin main
```

## Creating a release

Releases are created from tags. For example:

```powershell
git tag -a v1.1.0 -m "TypeBridge 1.1.0"
git push origin v1.1.0
```

Then attach the APK and the release zip on the GitHub release page
(or upload them through the API: `POST /repos/{owner}/{repo}/releases/{id}/assets`).
