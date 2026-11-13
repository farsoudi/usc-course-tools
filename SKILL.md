---
name: course-tools
description: Use when the user says "pull from brightspace", "check brightspace", "my grades", "what's due", "assignments", "submissions", "notifications", "get me up to date", "check Piazza", "check Gradescope", or otherwise asks about USC course tools. Also use when asked to set up, log in, refresh, or troubleshoot course-tools. Provides the local-login REST/Lite recipes for Brightspace (D2L), Piazza, and Gradescope.
compatibility: Requires Python 3.10+, Playwright, Chrome/Edge/Chromium, and a desktop session for interactive login.
---

# USC course-tools access runbook (Brightspace + Piazza + Gradescope)

## When to use me

Load this whenever the user wants anything from their USC course tools:
grades, due dates, assignments, announcements/notifications, course content,
exam dates, Piazza, or Gradescope. Trigger phrases include "pull from
brightspace", "check brightspace", "my grades", "what's due", "when's my exam",
"get me up to date", "check Piazza / Gradescope".

Also load this when the user asks to set up, log in, refresh, or troubleshoot
course-tools.

Do **not** use this for generic Brightspace questions about how the tool works —
only for acting on the user's own accounts.

## On invocation

If this skill is loaded with no request, say course-tools is ready and wait. If
the invocation included a request, treat it as the task.

## What this covers

This is the agent runbook for the user's USC course material. It covers all three
sources through the local auth store created by `scripts/auth.py`:
- **Brightspace** (`brightspace.usc.edu`, a D2L instance) — grades, assignments,
  announcements, content. REST API + cookie session.
- **Piazza** (`piazza.com`) — class Q&A / announcements. Read via the
  server-rendered **Lite** UI.
- **Gradescope** (`www.gradescope.com`) — assignment submissions and grades.

If the user asks to "check my grades", "check notifications", "what's due",
"when is my exam", "get me up to date", "check Piazza / Gradescope", etc. — use
the endpoints and recipes below. Do **not** use the VNC browser for this unless
the API is genuinely unavailable.

**READ-ONLY RULE (default):** only ever issue `GET` requests and read pages.
Never `POST`, submit, upload, edit, delete, mark-read, favorite, follow, or
otherwise perform an action on any of these services. When in doubt, don't.
**Sole exception:** submitting a file to a Brightspace **D2L dropbox** — and only
when the user *explicitly* asks to submit. See "Assignment submission" below.
Everything else (Piazza, Gradescope, grades, comments) stays read-only.

## Authentication (do this before reading)

Run these commands from the skill directory (the folder containing this
`SKILL.md`); the harness provides it as the skill base directory. Claude Code
exposes it as `${CLAUDE_SKILL_DIR}`. If the current directory is elsewhere, use
absolute paths.

Runtime setup — including installing Python, creating a venv, and installing
Playwright — is documented in `AGENTS.md`. Use the interpreter it prepares
(typically `<data-dir>/venv/bin/python`; Windows:
`<data-dir>\venv\Scripts\python.exe`). Commands below use `python3` as shorthand.

Credentials live **outside this repository** in the directory named by
`COURSE_TOOLS_DATA_DIR` (or the platform default — see `.env.dist`). Copy
`.env.dist` to `.env` only if you need to override it.

```bash
python3 scripts/auth.py login      # opens a browser; log in by hand
python3 scripts/auth.py status     # what is live / expired cookies
python3 scripts/auth.py path       # where auth.json lives
```

`login` captures the live browser session (cookies, including HttpOnly),
validates each service, and writes `auth.json` with mode `600`. If a call returns
401/403 or a login page, or `status` lists an expired cookie, run
`python3 scripts/auth.py login --service <name>` and retry. Never ask the user to
export or paste cookies. Windows is implemented but currently untested.

### First-time harness setup

Detect the harness and use its native command behavior:

- **Claude Code:** the installed skill is `/course-tools`; do nothing.
- **Codex:** use `$course-tools` or `/skills`; do nothing.
- **opencode:** if `~/.config/opencode/commands/course-tools.md` is missing, ask
  the user once: "Do you want a `/course-tools` shortcut?" If yes, create the
  file below; if no, skip it. Never overwrite an existing command file. Use the
  global path for a global install; use `.opencode/commands/` for a project-local
  install.
- **Other harnesses:** skip unless you know their command mechanism.

```md
---
description: Load the course-tools skill and wait for a request.
---

Use the `course-tools` skill. Load it with the skill tool.
User request (may be empty): $ARGUMENTS

If the request is empty, say course-tools is ready and wait. Otherwise, proceed.
```

## Files in this skill

- `scripts/auth.py` — login, status, and the local credential store.
- `scripts/submit_dropbox.py` — **the only write action**: submits one file to a
  D2L dropbox by driving the real browser UI (see "Assignment submission").
- `AGENTS.md` — one-time runtime setup (Python/Playwright/login).
- `.env.dist` — sample config; `.env` is ignored.
- Data dir (outside the repo): `auth.json` and `browser-profile/`.

Brightspace home URL: `https://brightspace.usc.edu/d2l/home`.

## Plumbing (copy-paste)

Requirements:
- Put `scripts/` on `sys.path` and use `auth.auth_headers(...)`, which returns
  the stored `Cookie` header for that service.
- Use a **full, modern User-Agent** (`auth.UA`). A stub UA makes Brightspace
  return an "Unsupported Browser" page (HTTP 200).
- API responses may start with the XSSI prefix `while(1);` — strip it before
  `json.loads`.
- All three services use the same helper; just change the service/host.

```python
import json, os, sys, urllib.request

# Set to this skill's directory (the folder containing SKILL.md).
SKILL = os.environ.get("COURSE_TOOLS_SKILL_DIR", "REPLACE_WITH_SKILL_DIR")
sys.path.insert(0, f"{SKILL}/scripts")
import auth

BASE = "https://brightspace.usc.edu"
HOST = "brightspace.usc.edu"

def raw(path, accept="application/json"):
    headers = {"User-Agent": auth.UA, "Accept": accept}
    headers.update(auth.auth_headers("brightspace", HOST))
    req = urllib.request.Request(BASE + path, headers=headers)
    return urllib.request.urlopen(req, timeout=30).read()

def jget(path):
    s = raw(path).decode("utf-8", "replace")
    if s.startswith("while(1);"):
        s = s[len("while(1);"):]
    return json.loads(s)
```

Set `SKILL` to the folder containing this `SKILL.md` (or export
`COURSE_TOOLS_SKILL_DIR`). Piazza: `auth.auth_headers("piazza", "piazza.com")`;
Gradescope: `auth.auth_headers("gradescope", "www.gradescope.com")`.

### Identity (derive at runtime)
- `user_id`: `users/whoami` -> `Identifier`.
- **home OU**: parse the homepage HTML (`D2L.LP.Notification.Settings.<ou>`,
  `/d2l/le/calendar/<ou>`). It is institution/account-specific; do not hardcode.

### Semester codes
Org-unit codes look like `20263_30593`. The first 5 digits are the term:
`20262` = Summer 2026, `20263` = Fall 2026, `20251` = Spring 2025, etc.
(`mysemesters` maps code -> name, e.g. `20263` -> "2026 Fall"). Filter
enrollments to the current term; derive it from `mysemesters`/the course codes,
and ask the user when unsure.

### Time
All datetimes from the API are UTC ISO-8601 (`...Z`). USC is **Pacific**
(PDT = UTC-7 in fall). Due times like `2026-09-14T06:59:59Z` = Sun 11:59 PM PDT.
Convert with `zoneinfo`/`pytz` before reporting.

## Endpoint catalog

Use API version `1.67` (also confirmed: `1.43`). `{ou}` = org unit id
(course offering id).

| Purpose | Endpoint |
|---|---|
| Who am I | `GET /d2l/api/lp/1.43/users/whoami` |
| My enrollments | `GET /d2l/api/lp/1.43/enrollments/myenrollments/?orgUnitTypeId=3` |
| My courses (homepage widget) | `GET /d2l/le/manageCourses/api/mycourses` |
| My terms/semesters | `GET /d2l/le/manageCourses/api/mysemesters` |
| Nav alert feed (notifications) | `GET /d2l/NavigationArea/{home_ou}/ActivityFeed/GetAlertsDaylight?Category=N` |
| Announcements (news) | `GET /d2l/api/le/1.67/{ou}/news/` |
| Assignments (dropbox) | `GET /d2l/api/le/1.67/{ou}/dropbox/folders/` |
| Quizzes | `GET /d2l/api/le/1.67/{ou}/quizzes/` |
| Discussions | `GET /d2l/api/le/1.67/{ou}/discussions/forums/` |
| My grades (released) | `GET /d2l/api/le/1.67/{ou}/grades/values/myGradeValues/` |
| Grade items (denominators) | `GET /d2l/api/le/1.67/{ou}/grades/` |
| Calendar events (date range) | `GET /d2l/api/le/1.67/{ou}/calendar/events/?startDateTime=<ISO>&endDateTime=<ISO>` |
| Course content tree | `GET /d2l/api/le/1.67/{ou}/content/toc` |
| Module detail (incl. description) | `GET /d2l/api/le/1.67/{ou}/content/modules/{moduleId}` |
| Content file download | `GET /content/enforced/{ou}-{term}_{section}/<filename>` |

Notes:
- **Auth:** every request uses the stored Brightspace cookie header. A stale
  session may return a 200 login HTML page, so validate by content-type/final
  host, not status.
- `users/whoami` returns `Identifier` (=user_id), `FirstName`, `LastName`, `UniqueName`.
- `enrollments/myenrollments` returns `Items[].OrgUnit` with `Id`, `Name`,
  `Code`, `HomeUrl`, plus `Access.LastAccessed`, `Access.ClasslistRoleName`.
  The `enrollments/.../pin` endpoint exists for pinning (not needed).
- `GetAlertsDaylight` **Category** mapping (confirmed from homepage
  `data-category` attrs): `0` = Subscriptions (discussions icon), `1` = Updates
  (notification bell — the usual "notifications"), `2` = Messages (email icon).
  Response is a D2L RPC JSON blob; the rendered notification HTML is at
  `Payload.Html` (strip tags; entries look like `"<Title>"`,
  `"<Type> - <Course name>"`, `"<relative time>"`).
- `news/` items: `Title`, `CreatedDate`, `Body.Text`/`Body.Html`,
  `Attachments[]`, `IsHidden`. Supports `?since=<ISO>` (returned same as no
  filter when nothing newer).
- `dropbox/folders/` items: `Id`, `Name`, `DueDate`, `IsHidden`,
  `GradeItemId`, `CustomInstructions`, `Attachments[]`. **This is where
  assignment due dates live.**
- `quizzes/` items (`Objects[]`): `Name`, `StartDate`, `DueDate`, `EndDate`.
  Often empty even when assignments exist.
- `grades/values/myGradeValues/`: `GradeObjectName`, `PointsNumerator`,
  `PointsDenominator`, `DisplayedGrade`, `Comments`. Returns `[]` when nothing
  is released yet. (Final-grade endpoint not confirmed.)
- `calendar/events/` items: `Title`, `Description`, `StartDateTime`,
  `EndDateTime`, `CalendarEventViewUrl`, `OrgUnitId`. Use a wide range
  (`...T00:00:00.000Z`). The undocumented `myEvents/` sub-path 400s.
- `content/toc`: top-level `Modules[]`; each module has `ModuleId`, `Title`,
  `Description`, `Topics[]` (`Title`, `Url`), and nested `Modules[]`. This is
  the richest single call per course.
- Files under `/content/enforced/...` are served directly (scheme-less
  `DefaultPath` is `/content/enforced/{ou}-{code}/`). PDFs/DOCX/ZIP/HTML all
  download in cookie mode. HTML topics are the assignment questions; PDFs are
  manuals/syllabi.

## Task recipes

### Notifications ("latest notifications")
```
raw("/d2l/NavigationArea/{home_ou}/ActivityFeed/GetAlertsDaylight?Category=1")
```
Derive `{home_ou}` from the homepage HTML. Strip `while(1);`, `json.loads`, take
`Payload.Html`, strip HTML tags, and read the grouped triples (title / "Type -
Course" / relative time). `Category=1` is the bell; use `2` for messages, `0`
for subscriptions.

### Grades ("how am I doing" / "check my grades")
Loop current-semester enrollments and call
`grades/values/myGradeValues/` per `{ou}`. Each row: name + `DisplayedGrade`
(+ `PointsNumerator/Denominator`). `[]` means no released grades for that
course (not an error). Course-wide grade item weights/denominators come from
`grades/`.

### "What is due in the next week across all my classes"
For each current-semester `{ou}`:
1. `dropbox/folders/` -> assignment `Name` + `DueDate`.
2. `quizzes/` -> quiz `Name` + `DueDate`/`StartDate`.
3. `calendar/events/?startDateTime=now&endDateTime=now+7d` -> other events.
Merge, convert UTC->PT, filter to `[now, now+7d]`, sort, label by course. This
is authoritative and avoids relying on the JS homepage widgets.

### "When is my exam?"
Exam dates usually live in a Content module named **Syllabus** or
**Exam Guidelines** (module **Description**), and/or in announcements, and/or
a schedule PDF. Recipe:
1. `content/toc`; recursively find modules whose title matches
   `exam|midterm|final|syllabus|schedule`.
2. `content/modules/{moduleId}` -> read `Description.Html`/`Text`.
3. Also `news/` announcements and any syllabus/schedule PDFs (download and
   `pdftotext`).
Example (EE-477 `ou=301851`): module "Exam Guidelines" description contained
"Exam 1: Monday, October 5, 6-7:30pm in THH 201; Exam 2: Monday, November 30...".

### "Get me up to date"
Combine: nav notifications (`Category=1`), recent `news/` per current course
(`CreatedDate` desc), and due-soon sweep (recipe above). Summarize by course.
For **CSCI-467** also read the public site (deadlines/exams) and Piazza Lite
(`/lite/feed` for announcements); check Gradescope for submission status. For
any course, Gradescope `/courses/{id}` shows submitted/released state.

### Course content / read a homework
`content/toc` -> find the module (e.g. `Assignments > HWs > HW 1`), download
each topic `Url` from `/content/enforced/...`. Question texts are HTML topics
(e.g. `Q1 - 20 Points.html`); figures/equations are embedded `<img>` (report
that they exist; download and view if needed). Note: assignment **instructions
attachments** may be empty in the dropbox itself — the real content is under
Content.

## Assignment submission (write action — ONLY when the user explicitly asks)

`{ou}` = course org unit (derive from `enrollments`).
`{db}` = dropbox folder Id from `GET /d2l/api/le/1.67/{ou}/dropbox/folders/`,
matched on `Name`. Always show the user the resolved folder + file before firing.

**Use `scripts/submit_dropbox.py` — never replay the HTTP flow by hand.**
Run `python3 scripts/auth.py login` first.

```bash
python3 scripts/submit_dropbox.py --ou <ou> --db <db> --file report.pdf
python3 scripts/submit_dropbox.py --ou <ou> --db <db> --file report.pdf --dry-run
python3 scripts/submit_dropbox.py --ou <ou> --db <db> --file report.pdf --verify-only
```

It drives installed Chrome/Edge (or bundled Chromium), then reads the submission
back from the API. `--dry-run` stages the upload and stops before Submit;
`--verify-only` just reads back what is already there.

### Why a browser and not HTTP

Replaying D2L's upload POST **does not work.** `POST
/d2l/lp/fileupload/{ou}?direct=true&maxFileSize=...&isLastSlice=true` returns
`403 You do not have permission to view this directory or page.` — with valid
session cookies, with `Referer`/`Origin`/`X-Requested-With` added, and with the
exact HAR-recorded multipart field layout. `d2l_hitCode` (and much of
`d2l_state`/`d2l_controlMap`) is minted by page JS, so a hand-built POST cannot
satisfy the server. A previous HAR-derived 4-call recipe lived here; it was
never replayed successfully and is superseded by this section.

### The UI flow the script automates

1. `GET /d2l/lms/dropbox/user/folder_submit_files.d2l?ou={ou}&db={db}`.
   Title is `<assignment> - <course> - USC`; if the body says `Sign in`, the
   session expired — run `python3 scripts/auth.py login --service brightspace`.
2. Click `#z_p` ("Add a File").
3. Wait for the modal iframe whose URL contains `dialogs/file/main.d2l`.
4. The dialog opens on a **source picker** (My Computer / My Locker / Group
   Locker / OneDrive / Google Drive) — *not* the uploader. Click the `<a>` whose
   text starts with `My Computer` to reveal it. That anchor's id is regenerated
   on every load, so find it by text, not by id.
5. Inside `page.expect_file_chooser()`, click the `button` whose text is exactly
   `Upload`, then `chooser.set_files(path)`.
6. Poll the dialog body until the filename appears (a 3.5 MB file took ~6–11 s).
7. **Gotcha:** the modal footer — `Add` / `Back` / `Cancel` — lives in the
   **parent frame**, not the dialog iframe. Click `Add` on `page.main_frame`.
   The page has two `Cancel` buttons, so match exact text.
8. The page should now read `(1) file(s) to submit` plus the filename.
9. Click `Submit` (`button.d2l-button`, id `z_a`) inside
   `page.expect_navigation()` → lands on
   `folder_submit_files_results.d2l?...&sid=<id>` reading
   `File submission successful | Submission ID <id>`.

Use a raw DOM `.click()` rather than `frame.click()` — D2L re-renders these
controls and Playwright's actionability checks time out on them.

### Always verify with the API, not the result page

`GET /d2l/api/le/1.67/{ou}/dropbox/folders/{db}/submissions/` — a plain GET using
the local auth store — returns one entry per student:
`{Entity, Status, Submissions:[{Id, SubmittedBy, SubmissionDate, Files:[...]}]}`.
`Status: 1` means submitted, and `SubmissionDate` is UTC. Confirm the `FileName`
matches what you sent before telling the user it worked; the local result page is
not sufficient proof on its own.

## Course org-unit ids
Derive at runtime: `GET enrollments/myenrollments/?orgUnitTypeId=3`, then filter
`Code.startswith("<current term>")`. Do not hardcode course ids.

### Courses that don't live in Brightspace
- **CSCI-467** (Foundations of Machine Learning, ou `301999`) does **not** use
  Brightspace beyond announcements — assignments, schedule, lecture notes, and
  exams are on the public course website **https://usc-csci467.github.io/**.
  Submissions go through **Gradescope** (course `1366005`). Always check this
  site (not `dropbox/`/`quizzes/`) for CSCI-467 deadlines. Grading: HW 31%,
  project 18%, oral 6%, exams 45%; 6 late days (max 3/assignment, not on the
  final project report).

## Piazza (Q&A / announcements)

Auth: `auth.auth_headers("piazza", "piazza.com")`. Same modern-UA recipe.
**Read-only.**

The full app URL `https://piazza.com/class/{nid}` is a **JS single-page app** —
its content is loaded through **POST** RPC calls (`network.get_my_feed`,
`network.filter_feed`, `content.get`, ...), so it is **not** usable for
read-only scraping. **Do not** hit those RPCs (they are POSTs).

Instead read the **server-rendered Lite UI**, which is plain `GET` HTML:

| Purpose | URL |
|---|---|
| Feed (default) | `GET https://piazza.com/lite/` (redirects to `/lite/feed`) |
| Filtered feed | `GET /lite/feed?filter=unread` (also `unanswered`, `unresolved_followups`) |
| Read a post | `GET /lite/posts/{postId}` |
| Course from signup link | `GET /usc/fall2026/csci467` → redirects to `/class?nid={nid}` |

Notes:
- The **nid** (network id) is exposed by following the redirect from the
  `/usc/{term}/{slug}` signup URL.
- `/lite/feed` renders unread counts, a "class at a glance" summary, and a table
  of posts (subject, type note/question, tags, content snippet, post time) whose
  rows link to `/lite/posts/{id}`. Strip HTML tags to read the text.
- `/lite/account` and `/lite/classes` 404; the Lite feed targets the current
  logged-in class directly.

## Gradescope (submissions + grades)

Auth: `auth.auth_headers("gradescope", "www.gradescope.com")`. Same recipe.
**Read-only — never submit/upload.**

| Purpose | URL |
|---|---|
| Dashboard ("Your Courses") | `GET https://www.gradescope.com/` |
| Course dashboard | `GET /courses/{courseId}` |
| Assignment view / submit | `GET /courses/{courseId}/assignments/{assignmentId}` |
| Regrade requests | `GET /courses/{courseId}/regrade_requests` |
| Submission | `/courses/{courseId}/assignments/{aid}/submissions/{sid}` |

Notes:
- The root page is the **course list**, grouped by term, each with course name,
  id, and "N assignments" (parse course ids from `href="/courses/{id}"`).
- A course page (`/courses/{id}`) has an **assignment table**: `Name`, `Status`
  (e.g. `Submitted`), a `Released` grade/lateness column, `Release Date`,
  `Due Date`, and `Late Due Date`. Dates are already shown in **PDT**. Row
  submission links look like `/courses/{id}/assignments/{aid}/submissions/{sid}`.
- The assignment page is either a "View Submission" (graded/submitted) or a
  "Submit ... Assignment" upload form — read it, never upload.
- No JSON API confirmed (`/api/v1/courses/{id}/assignments` → 404); scrape the
  HTML tables.
- Parse course ids from `href="/courses/{id}"`; do not hardcode them.
- Ignore past-term courses unless the user explicitly asks about them. Determine
  the current term from the dashboard and only report that term by default.

## Caveats / gotchas
- Run `python3 scripts/auth.py status` first. If a service is expired, run
  `python3 scripts/auth.py login --service <name>` and retry. See `AGENTS.md`
  for runtime setup if Python or Playwright is missing.
- All endpoints use the same cookie header. A stale session may return HTTP 200
  with login HTML, so detect login pages rather than trusting status codes.
- Modern User-Agent is mandatory (else "Unsupported Browser").
- API `1.67` and `1.43` both work; `manageCourses/*` is unversioned.
- Notifications are on the **home OU**, not a course OU.
- Never store `auth.json` in this repository; it lives in `COURSE_TOOLS_DATA_DIR`.
- Some responses prefix `while(1);` — strip before parsing.
- Times are UTC; convert to Pacific before telling the user.
- `myGradeValues`/`quizzes` returning `[]` is normal (nothing released/posted).
- Announcements are called **news** in the API.
