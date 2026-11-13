# Agent setup: course-tools

The user installed this skill (usually with `npx skills add`). That only placed
the files. Do the runtime setup yourself; the user should not have to run Python
commands.

## 1. Locate the skill and data directory

Work from the directory containing `SKILL.md` (the harness provides it; Claude
Code exposes it as `${CLAUDE_SKILL_DIR}`).

The data directory is `COURSE_TOOLS_DATA_DIR` if set, otherwise:

| OS | Default |
|---|---|
| Linux | `~/.local/share/course-tools/` |
| macOS | `~/Library/Application Support/course-tools/` |
| Windows | `%LOCALAPPDATA%\course-tools\` |

Once Python is available you can ask the script: `python3 scripts/auth.py path`.
Never put credentials in the skill directory.

## 2. Ensure Python 3.10+

Check `python3 --version` (Windows: `py -3 --version`). If missing, install it;
ask for approval before using sudo or a system installer.

| OS | Suggested install |
|---|---|
| Debian/Ubuntu | `sudo apt-get install -y python3 python3-venv python3-pip` |
| Fedora | `sudo dnf install -y python3 python3-pip` |
| Arch | `sudo pacman -S --needed python python-pip` |
| macOS | `brew install python`, or `xcode-select --install` |
| Windows | `winget install Python.Python.3.12` |

## 3. Create a venv and install Playwright

Keep the environment outside the skill and repo, under the data directory.

Linux/macOS:

```bash
if [ -n "$COURSE_TOOLS_DATA_DIR" ]; then
  DATA="$COURSE_TOOLS_DATA_DIR"
elif [ "$(uname -s)" = "Darwin" ]; then
  DATA="$HOME/Library/Application Support/course-tools"
else
  DATA="$HOME/.local/share/course-tools"
fi
python3 -m venv "$DATA/venv"
"$DATA/venv/bin/python" -m pip install --upgrade pip playwright
PY="$DATA/venv/bin/python"
```

Windows PowerShell:

```powershell
$Data = if ($env:COURSE_TOOLS_DATA_DIR) { $env:COURSE_TOOLS_DATA_DIR } else { Join-Path $env:LOCALAPPDATA "course-tools" }
py -3 -m venv "$Data\venv"
& "$Data\venv\Scripts\python.exe" -m pip install --upgrade pip playwright
$PY = "$Data\venv\Scripts\python.exe"
```

If the user already has Chrome or Edge, do not download another browser. Only if
both are absent:

```bash
"$PY" -m playwright install chromium
```

## 4. Log in and validate

Run this from the skill directory, on a desktop session with a display:

```bash
"$PY" scripts/auth.py login
"$PY" scripts/auth.py status
```

Log in normally (SSO/MFA included). If a service is expired later, rerun
`"$PY" scripts/auth.py login --service <name>` and validate again.

If there is no display (SSH/CI/cloud session), explain that the interactive login
must run on the user's desktop; do not attempt a headless login.

## 5. Harness command (ask only when needed)

- **Claude Code:** nothing to do. The installed skill is `/course-tools`.
- **Codex:** nothing to do. Use `$course-tools` or `/skills`.
- **opencode:** check `~/.config/opencode/commands/course-tools.md`. If it is
  missing, ask the user once: "Do you want a `/course-tools` shortcut?" If yes,
  create the file; if no, skip it. Never overwrite an existing command file.
  Use the global path for a global install; use `.opencode/commands/` for a
  project-local install.
- **Other harnesses:** skip unless you know their command mechanism.

```md
---
description: Load the course-tools skill and wait for a request.
---

Use the `course-tools` skill. Load it with the skill tool.
User request (may be empty): $ARGUMENTS

If the request is empty, say course-tools is ready and wait. Otherwise, proceed.
```

## Rules

- Do not ask the user to install Python, Playwright, or a browser.
- Do not create the opencode command without asking first.
- Do not prompt Claude Code or Codex for a command; they already invoke the skill natively.
- Do not print or commit cookie values; `auth.json` is a credential.
- Keep credentials and the venv in the data directory, never in the repo.
- Follow the read-only rules in `SKILL.md`; only submit files when explicitly asked.
- Windows setup is implemented but untested; report failures plainly.
