#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Kasra Farsoudi
"""Log in to USC course tools and cache the resulting session locally.

    python3 scripts/auth.py login
    python3 scripts/auth.py status
    python3 scripts/auth.py path

The browser window is a normal Chrome/Edge/Chromium window using a dedicated
profile under the course-tools data directory. Log in by hand; the script waits,
captures cookies (including HttpOnly), validates them, and writes only validated
credentials.

Secrets are stored outside this repository, at COURSE_TOOLS_DATA_DIR or the
platform default. Windows support is implemented but untested.

Requires Python 3.10+ and Playwright. Agent setup is documented in AGENTS.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

SERVICES: dict[str, dict[str, str]] = {
    "brightspace": {
        "label": "Brightspace",
        "host": "brightspace.usc.edu",
        "login_url": "https://brightspace.usc.edu/d2l/home",
    },
    "piazza": {
        "label": "Piazza",
        "host": "piazza.com",
        "login_url": "https://piazza.com/lite/feed",
    },
    "gradescope": {
        "label": "Gradescope",
        "host": "www.gradescope.com",
        "login_url": "https://www.gradescope.com/",
    },
}

COOKIE_NAMES: dict[str, set[str]] = {
    "brightspace": {
        "d2lSessionVal",
        "d2lSecureSessionVal",
        "d2lSameSiteCanaryA",
        "d2lSameSiteCanaryB",
    },
    "piazza": {"session_id", "piazza_session", "last_piaz_user"},
    "gradescope": {"_gradescope_session", "signed_token"},
}

AUTH_VERSION = 1


def _load_dotenv() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def data_dir() -> Path:
    _load_dotenv()
    override = os.environ.get("COURSE_TOOLS_DATA_DIR", "").strip()
    if override:
        path = Path(override).expanduser().resolve()
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "course-tools"
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / "course-tools"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = base / "course-tools"
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def auth_path() -> Path:
    return data_dir() / "auth.json"


def profile_dir() -> Path:
    path = data_dir() / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_auth() -> dict[str, Any]:
    path = auth_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": AUTH_VERSION}
    return data if isinstance(data, dict) else {"version": AUTH_VERSION}


def save_auth(data: dict[str, Any]) -> Path:
    path = auth_path()
    tmp = path.with_suffix(".json.tmp")
    data = dict(data)
    data.setdefault("version", AUTH_VERSION)
    data["captured_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _domain_matches(host: str, cookie_domain: str) -> bool:
    domain = (cookie_domain or "").lstrip(".").lower()
    host = (host or "").lower()
    return bool(domain) and (host == domain or host.endswith("." + domain))


def _relevant_cookie(service: str, name: str, cookie_domain: str) -> bool:
    domain = (cookie_domain or "").lstrip(".").lower()
    if service == "brightspace":
        domain_ok = domain == "brightspace.usc.edu"
    elif service == "piazza":
        domain_ok = domain == "piazza.com" or domain.endswith(".piazza.com")
    elif service == "gradescope":
        domain_ok = domain == "gradescope.com" or domain.endswith(".gradescope.com")
    else:
        domain_ok = False
    return domain_ok and name in COOKIE_NAMES.get(service, set())


def expired_cookies(service: str, data: dict[str, Any] | None = None) -> list[str]:
    data = data if data is not None else load_auth()
    entry = data.get(service) or {}
    now = time.time()
    names = []
    allowed = COOKIE_NAMES.get(service, set())
    for cookie in entry.get("cookies") or []:
        name = cookie.get("name")
        expires = cookie.get("expires")
        if name in allowed and isinstance(expires, (int, float)) and expires > 0 and expires < now:
            names.append(name)
    return names


def _cookie_header_from_entry(
    entry: dict[str, Any] | None,
    host: str,
    allowed: set[str] | None = None,
) -> str:
    now = time.time()
    parts: list[str] = []
    for cookie in (entry or {}).get("cookies") or []:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        if allowed is not None and name not in allowed:
            continue
        if not _domain_matches(host, cookie.get("domain", "")):
            continue
        expires = cookie.get("expires")
        if isinstance(expires, (int, float)) and expires > 0 and expires < now:
            continue
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def cookie_header(
    service: str,
    host: str | None = None,
    data: dict[str, Any] | None = None,
) -> str:
    data = data if data is not None else load_auth()
    host = host or SERVICES[service]["host"]
    return _cookie_header_from_entry(
        data.get(service) or {}, host, allowed=COOKIE_NAMES.get(service, set())
    )


def auth_headers(
    service: str,
    host: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, str]:
    cookie = cookie_header(service, host, data=data)
    return {"Cookie": cookie} if cookie else {}


def _request(
    url: str,
    service: str,
    host: str | None = None,
    timeout: int = 20,
    data: dict[str, Any] | None = None,
) -> tuple[int, str, str, str]:
    headers = {"User-Agent": UA, "Accept": "application/json,text/html,*/*"}
    headers.update(auth_headers(service, host, data=data))
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(2_000_000).decode("utf-8", "replace")
            return response.status, response.geturl(), response.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as exc:
        body = exc.read(200_000).decode("utf-8", "replace")
        return exc.code, exc.geturl(), exc.headers.get("Content-Type", ""), body


def validate(
    service: str,
    timeout: int = 20,
    data: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    data = data if data is not None else load_auth()

    if service == "brightspace":
        cookie = cookie_header("brightspace", "brightspace.usc.edu", data=data)
        if not cookie:
            return False, "not logged in"
        req = urllib.request.Request(
            "https://brightspace.usc.edu/d2l/api/lp/1.43/users/whoami",
            headers={"User-Agent": UA, "Accept": "application/json", "Cookie": cookie},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read(200_000).decode("utf-8", "replace")
            if body.startswith("while(1);"):
                body = body[len("while(1);"):]
            parsed = json.loads(body)
            if parsed.get("Identifier"):
                return True, "ok (cookie)"
            return False, "invalid whoami response"
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except Exception as exc:
            return False, str(exc)

    if service == "piazza":
        if not cookie_header("piazza", "piazza.com", data=data):
            return False, "not logged in"
        status, final, _, body = _request(
            "https://piazza.com/lite/feed",
            "piazza",
            "piazza.com",
            timeout=timeout,
            data=data,
        )
        if status != 200:
            return False, f"HTTP {status}"
        if "login" in final.lower() or "sign in" in body[:4000].lower():
            return False, "login required"
        return True, "ok (cookie)"

    if service == "gradescope":
        if not cookie_header("gradescope", "www.gradescope.com", data=data):
            return False, "not logged in"
        status, final, _, body = _request(
            "https://www.gradescope.com/",
            "gradescope",
            "www.gradescope.com",
            timeout=timeout,
            data=data,
        )
        if status != 200:
            return False, f"HTTP {status}"
        if "login" in final.lower() or "sign in" in body[:4000].lower():
            return False, "login required"
        if "your courses" not in body.lower() and 'href="/courses/' not in body:
            return False, "unexpected dashboard page"
        return True, "ok (cookie)"

    return False, "unknown service"


def _print_status(services: list[str], as_json: bool) -> int:
    results: dict[str, Any] = {}
    all_ok = True
    for service in services:
        entry = load_auth().get(service)
        if not entry:
            results[service] = {"ok": False, "detail": "not logged in"}
            all_ok = False
            continue
        try:
            ok, detail = validate(service)
        except Exception as exc:
            ok, detail = False, str(exc)
        expired = expired_cookies(service)
        if expired:
            ok = False
            names = ", ".join(expired)
            detail = f"expired cookie(s): {names}" if detail == "ok (cookie)" else f"{detail}; expired: {names}"
        result: dict[str, Any] = {"ok": ok, "detail": detail, "expired_cookies": expired}
        results[service] = result
        all_ok = all_ok and ok

    if as_json:
        print(json.dumps({"data_dir": str(data_dir()), "auth_file": str(auth_path()), "services": results}, indent=2))
    else:
        print(f"data: {data_dir()}")
        print(f"auth: {auth_path()}")
        for service in services:
            result = results[service]
            mark = "OK" if result["ok"] else "EXPIRED"
            print(f"{SERVICES[service]['label']:<12} {mark:<8} {result['detail']}")
        if not all_ok:
            print("\nRun: python3 scripts/auth.py login [--service NAME]")
    return 0 if all_ok else 1


def _browser_paths() -> dict[str, list[str]]:
    paths = {
        "chrome": [
            "google-chrome",
            "google-chrome-stable",
            "/opt/google/chrome/chrome",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ],
        "edge": [
            "microsoft-edge",
            "microsoft-edge-stable",
            "/opt/microsoft/msedge/msedge",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
    }
    if os.name == "nt":
        paths["chrome"] += [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        paths["edge"] += [
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
        ]
    return paths


def _browser_exists(name: str) -> bool:
    for candidate in _browser_paths()[name]:
        if os.path.isabs(candidate):
            if Path(candidate).exists():
                return True
        elif shutil.which(candidate):
            return True
    return False


def pick_browser(choice: str = "auto") -> str | None:
    choice = (choice or "auto").lower()
    if choice not in ("auto", "chrome", "edge", "chromium"):
        raise SystemExit("--browser must be auto, chrome, edge, or chromium")
    if choice == "auto":
        if _browser_exists("chrome"):
            return "chrome"
        if _browser_exists("edge"):
            return "msedge"
        return None
    if choice == "chromium":
        return None
    if not _browser_exists(choice):
        raise SystemExit(f"{choice} is not installed; use --browser chromium or install it")
    return "chrome" if choice == "chrome" else "msedge"


def _cookie_names(context: Any) -> set[str]:
    now = time.time()
    names = set()
    for cookie in context.cookies():
        expires = cookie.get("expires", -1)
        if isinstance(expires, (int, float)) and expires > 0 and expires < now:
            continue
        names.add(cookie.get("name", ""))
    return names


def _logged_in(service: str, context: Any, page: Any) -> bool:
    url = (page.url or "").lower()
    names = _cookie_names(context)
    if service == "brightspace":
        if any(
            marker in url
            for marker in (
                "login.microsoftonline.com",
                "login.usc.edu",
                "/d2l/login",
                "/d2l/lp/auth/saml",
            )
        ):
            return False
        return "d2lSessionVal" in names and "login" not in url
    if service == "piazza":
        return "session_id" in names and "login" not in url
    if service == "gradescope":
        return "_gradescope_session" in names and "login" not in url
    return False


def _capture(service: str, context: Any) -> dict[str, Any]:
    cookies = []
    now = time.time()
    for cookie in context.cookies():
        if not _relevant_cookie(service, cookie.get("name", ""), cookie.get("domain", "")):
            continue
        expires = cookie.get("expires", -1)
        if isinstance(expires, (int, float)) and expires > 0 and expires < now:
            continue
        cookies.append(
            {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain"),
                "path": cookie.get("path", "/"),
                "expires": cookie.get("expires", -1),
                "http_only": bool(cookie.get("httpOnly")),
                "secure": bool(cookie.get("secure")),
                "same_site": cookie.get("sameSite"),
            }
        )
    return {"cookies": cookies}


def login(services: list[str], browser: str, timeout: int) -> int:
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        raise SystemExit("No graphical display detected. Run this on a desktop session.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "playwright is not installed.\n"
            "Ask your agent to run the setup in AGENTS.md, or install it with:\n"
            "  python3 -m pip install playwright"
        )

    channel = pick_browser(browser)
    label = channel or "bundled chromium"
    print(f"browser: {label}")
    print(f"data:    {data_dir()}")

    existing = load_auth()
    results: dict[str, tuple[bool, str]] = {}

    with sync_playwright() as p:
        kwargs: dict[str, Any] = {
            "user_data_dir": str(profile_dir()),
            "headless": False,
        }
        if channel:
            kwargs["channel"] = channel
        try:
            context = p.chromium.launch_persistent_context(**kwargs)
        except Exception as exc:
            if channel:
                raise SystemExit(
                    f"could not launch {label}: {exc}\n"
                    "Try: python3 scripts/auth.py login --browser chromium"
                )
            raise SystemExit(
                "bundled Chromium is not installed.\n"
                "  python3 -m playwright install chromium"
            )

        try:
            for service in services:
                info = SERVICES[service]
                print(f"\n{info['label']}: {info['login_url']}")
                print(f"  log in if needed; waiting up to {timeout}s...")
                page = context.new_page()
                try:
                    page.goto(info["login_url"], wait_until="domcontentloaded", timeout=60_000)
                except Exception as exc:
                    print(f"  could not open page: {exc}")
                    page.close()
                    results[service] = (False, "could not open page")
                    continue

                deadline = time.time() + timeout
                while time.time() < deadline:
                    if page.is_closed():
                        break
                    try:
                        if _logged_in(service, context, page):
                            break
                    except Exception:
                        pass
                    page.wait_for_timeout(500)
                else:
                    print("  timed out waiting for login")
                    page.close()
                    results[service] = (False, "timed out")
                    continue

                if page.is_closed():
                    print("  page was closed")
                    results[service] = (False, "page closed")
                    continue

                entry = _capture(service, context)
                try:
                    ok, detail = validate(service, data={service: entry})
                except Exception as exc:
                    ok, detail = False, str(exc)
                results[service] = (ok, detail)
                if ok:
                    existing[service] = entry
                    existing[service]["validated_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                    print(f"  {detail}")
                elif service not in existing:
                    existing[service] = entry
                    print(f"  captured but not validated: {detail}")
                else:
                    print(f"  new session failed validation ({detail}); keeping the previous one")
                page.close()
        finally:
            context.close()

    path = save_auth(existing)
    print(f"\nsaved: {path}")
    for service in services:
        ok, detail = results.get(service, (False, "not attempted"))
        print(f"  {SERVICES[service]['label']:<12} {'OK' if ok else 'NOT OK':<7} {detail}")
    return 0 if all(r[0] for r in results.values()) else 1


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="USC course-tools authentication")
    sub = parser.add_subparsers(dest="command", required=True)

    login_parser = sub.add_parser("login", help="open a browser and capture cookies")
    login_parser.add_argument("--service", action="append", choices=list(SERVICES))
    login_parser.add_argument(
        "--browser",
        default=os.environ.get("COURSE_TOOLS_BROWSER", "auto"),
        choices=["auto", "chrome", "edge", "chromium"],
    )
    login_parser.add_argument("--timeout", type=int, default=600)
    login_parser.add_argument("--data-dir")

    status_parser = sub.add_parser("status", help="validate cached credentials")
    status_parser.add_argument("--service", action="append", choices=list(SERVICES))
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--data-dir")

    path_parser = sub.add_parser("path", help="print the credential directory")
    path_parser.add_argument("--json", action="store_true")
    path_parser.add_argument("--data-dir")

    args = parser.parse_args(argv)
    if getattr(args, "data_dir", None):
        os.environ["COURSE_TOOLS_DATA_DIR"] = args.data_dir

    if args.command == "login":
        return login(args.service or list(SERVICES), args.browser, args.timeout)

    if args.command == "status":
        services = args.service or list(SERVICES)
        if not auth_path().exists():
            if args.json:
                print(json.dumps({"data_dir": str(data_dir()), "auth_file": str(auth_path()), "services": {}}))
            else:
                print(f"no auth file yet: {auth_path()}")
                print("Run: python3 scripts/auth.py login")
            return 1
        return _print_status(services, args.json)

    if args.command == "path":
        data = {"data_dir": str(data_dir()), "auth_file": str(auth_path()), "profile": str(profile_dir())}
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            for key, value in data.items():
                print(f"{key}: {value}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
