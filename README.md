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
- "How are my grades in EE-477?"
- "How's the curve looking in CSCI-103?"
- "What's due in BUAD-304 this week?"
- "Anything new in my course announcements?"
- "What are students asking the professor on Piazza?"
- "When is my next Gradescope assignment due?"
- "Pull my graded MATH-407 exam and help me draft a regrade request"
- "Submit an assignment to my Brightspace dropbox"
- "Pull all of Puvvada's lecture material into a new directory, and generate a lecture html"

## Install

Run one command for the agent you use.

**opencode**

```bash
npx skills add farsoudi/usc-course-tools -g -a opencode -y
```

**Claude Code**

```bash
npx skills add farsoudi/usc-course-tools -g -a claude-code -y
```

**Codex**

```bash
npx skills add farsoudi/usc-course-tools -g -a codex -y
```

That installs the skill. The first time you use it, your agent finishes setup and
opens the login window. The command needs Node.js 22.20 or newer; if `npx` is
missing, install Node or ask your agent to. Add `--copy` if you prefer copied
files over symlinks.

## First run

After installing, ask your agent:

> set up course-tools and log me in

The agent reads `AGENTS.md`, installs any missing runtime (Python, Playwright,
and Chromium if needed), and opens a browser window for the USC login. Log in
normally, including SSO/MFA. You never need to install Python or run Python
commands yourself.

In opencode, setup also asks whether you want a `/course-tools` shortcut. Claude
Code and Codex already have native invocation, so they skip that question.

## Where credentials live

Outside this repository, in `COURSE_TOOLS_DATA_DIR` or the platform default:

| OS | Default |
|---|---|
| Linux | `~/.local/share/course-tools/` |
| macOS | `~/Library/Application Support/course-tools/` |
| Windows | `%LOCALAPPDATA%\course-tools\` |

`auth.json` is written with mode `600`; the browser profile lives in the same
directory. Credentials are never committed.

## Platforms

Linux and macOS are the tested targets. Windows support (paths, browser
detection, credential storage) is implemented but **untested**.

## Privacy

- Credentials stay on the machine and are only sent to the three course services.
- `auth.json` contains live session cookies; treat it like a password.
- Do not sync the data directory to untrusted hosts.

## For agents

- `AGENTS.md` — one-time runtime setup and login instructions.
- `SKILL.md` — the technical runbook: endpoints, read-only rules, and submission
  workflow.

Humans do not need to read either file.
