# course-tools

<p align="center">
  <img src="usc-course-tools.png" alt="usc-course-tools-logo" width="70%" />
</p>

An Agent Skill for USC course material — Brightspace, Piazza, and Gradescope.

It lets your agent work with your USC Brightspace (D2L) courses, Piazza classes,
and Gradescope assignments: grades, due dates, announcements, course content,
Piazza posts, and submission status. A one-time browser login gives it read-only
access. The only write action is a dropbox submission you explicitly ask for.

## What you can ask

- "What's due this week across my USC classes?"
- "How am I doing in EE-477 on Brightspace?"
- "Anything new in my CSCI-467 announcements?"
- "What's new on Piazza?"
- "When is my next Gradescope assignment due?"
- "Submit report.pdf to Lab 2"

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Google Chrome, Microsoft Edge, or Playwright's bundled Chromium
- A desktop session — login opens a real browser window

## Quick start

1. Install the skill for your harness (see below).
2. Log in:

   ```bash
   uv run scripts/auth.py login
   ```

3. Check what is live:

   ```bash
   uv run scripts/auth.py status
   ```

`login` opens a dedicated browser profile. Log in normally, including SSO/MFA.
The script waits, captures cookies, validates each service, and saves them outside
this repository. No cookie-export extension is needed. Rerun
`login --service brightspace` when a session expires.

Without uv:

```bash
python3 -m pip install playwright
python3 scripts/auth.py login
```

If Chrome and Edge are both missing, install Playwright's Chromium once:

```bash
uvx playwright install chromium          # uv
python3 -m playwright install chromium   # pip
```

## Install

Copy the whole `course-tools` folder into the skills directory for the harness
you use. No symlinks are required.

| Harness | Where to put it |
|---|---|
| opencode | `~/.config/opencode/skills/course-tools` (or `.opencode/skills/`) |
| Claude Code | `~/.claude/skills/course-tools` (or `.claude/skills/`) |
| Codex | `~/.agents/skills/course-tools` (or `.agents/skills/`) |
| Other Agent Skills hosts | Any path that expects `<name>/SKILL.md` |

If you are already talking to an agent, ask it to install the skill for its own
harness; it can copy the folder and handle the dependencies. Do not put this
under `~/.claude/skills/synced/` or Codex's `.system/` directory.

## Where credentials live

Outside this repository, in `COURSE_TOOLS_DATA_DIR` or the platform default:

| OS | Default |
|---|---|
| Linux | `~/.local/share/course-tools/` |
| macOS | `~/Library/Application Support/course-tools/` |
| Windows | `%LOCALAPPDATA%\course-tools\` |

`auth.json` is written with mode `600`; the browser profile lives in the same
directory. `.env` and `auth.json` are gitignored. Copy `.env.dist` to `.env` only
if you want to override the data directory or browser.

## Submitting files

Only when you explicitly ask:

```bash
uv run scripts/submit_dropbox.py --ou <course> --db <folder> --file <file>
```

The agent resolves the course and dropbox folder for you.

## Platforms

Linux and macOS are the tested targets. Windows support (paths, browser
detection, credential storage) is implemented but **untested**; please report
issues.

## Privacy

- Credentials stay on the machine and are only sent to the three course services.
- `auth.json` contains live session cookies; treat it like a password.
- Do not sync the data directory to untrusted hosts.

## Technical details

`SKILL.md` is the agent-facing runbook: endpoints, read-only rules, and the
submission workflow. Humans do not need to read it.
