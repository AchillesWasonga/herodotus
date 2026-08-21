import subprocess
import sys
from pathlib import Path

from flask import Flask, Response, render_template, request

from downloader import sanitize_filename


ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
DEFAULT_OUTPUT_DIR = ROOT / "downloads"
BROWSER_CHOICES = ["", "safari", "chrome", "firefox", "edge", "brave", "chromium"]

app = Flask(__name__, template_folder=str(SRC_DIR / "templates"))


def run_download_command(cmd: list[str]) -> tuple[bool, str]:
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    ).strip()
    if not combined:
        combined = "(No output)"
    return result.returncode == 0, combined


def last_meaningful_line(log: str) -> str:
    lines = [line.strip() for line in log.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def extract_saved_paths(log: str) -> list[tuple[str, str]]:
    extracted: list[tuple[str, str]] = []
    labels = {
        "Saved file:": "Video",
        "Metadata saved:": "Metadata",
    }
    for line in log.splitlines():
        stripped = line.strip()
        for prefix, label in labels.items():
            if stripped.startswith(prefix):
                extracted.append((label, stripped.removeprefix(prefix).strip()))
    return extracted


def source_access_blocked(log: str) -> bool:
    lowered = log.lower()
    signals = [
        "is not granting access",
        "empty media response",
        "check if this post is accessible in your browser",
        "login required",
        "requires a logged-in session",
        "blocked public access",
    ]
    return any(s in lowered for s in signals)


def source_unavailable(log: str) -> bool:
    lowered = log.lower()
    signals = [
        "requested content is not available",
        "page isn't available",
        "page may have been removed",
        "the link you followed may be broken",
        "video unavailable",
    ]
    return any(s in lowered for s in signals)


def build_result_payload(
    ok: bool,
    browser: str,
    output_dir: str,
    log: str,
    command: str,
) -> dict:
    payload = {
        "ok": ok,
        "title": "",
        "message": "",
        "command": command,
        "log": log,
        "saved_paths": extract_saved_paths(log),
        "tips": [],
        "technical_note": last_meaningful_line(log),
        "output_dir": output_dir or str(DEFAULT_OUTPUT_DIR),
    }

    lowered = log.lower()

    if ok:
        payload["title"] = "Download complete"
        payload["message"] = "Your video was downloaded successfully."
        if not payload["saved_paths"]:
            payload["tips"] = [
                f"Check the destination folder: {payload['output_dir']}",
            ]
        return payload

    if "ffmpeg is not installed" in lowered:
        payload["title"] = "ffmpeg is missing"
        payload["message"] = "The app cannot process video without ffmpeg installed."
        payload["tips"] = [
            "Install ffmpeg on this machine and retry.",
            "On macOS with Homebrew: brew install ffmpeg",
        ]
        return payload

    if source_unavailable(log):
        payload["title"] = "Video unavailable"
        payload["message"] = "The source is reporting that this video is not available."
        payload["tips"] = [
            "Open the link in a browser first to confirm it still exists.",
            "Ask for a fresh URL if the post may have been removed or changed.",
        ]
        return payload

    if source_access_blocked(log):
        payload["title"] = "Login required"
        if browser:
            payload["message"] = (
                f"The source would not serve this video through the selected {browser} session."
            )
            payload["tips"] = [
                f"Make sure you are logged in on this site in {browser} on this machine.",
                "Open the link in that same browser and confirm it plays there.",
                "If it still fails, try a different browser from the dropdown.",
            ]
        else:
            payload["message"] = "The source would not serve this video anonymously."
            payload["tips"] = [
                "Choose a browser in 'Browser Cookies'.",
                "Make sure that browser is already logged into the site.",
                "Then retry the download.",
            ]
        return payload

    if "download failed" in lowered:
        payload["title"] = "Download failed"
        payload["message"] = "The source did not complete successfully."
        payload["tips"] = [
            "Double-check the URL and try again.",
            "Test whether the video opens in a browser first.",
        ]
        return payload

    payload["title"] = "Something went wrong"
    payload["message"] = "The app could not complete this request."
    payload["tips"] = [
        "Review the technical details below.",
        "Retry once after confirming the URL and form values.",
    ]
    return payload


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status=204)


@app.route("/", methods=["GET", "POST"])
def index():
    state = {
        "url": "",
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "filename": "",
        "browser": "",
    }
    result = {
        "ok": None,
        "title": "",
        "message": "",
        "log": "",
        "command": "",
        "saved_paths": [],
        "tips": [],
        "technical_note": "",
        "output_dir": str(DEFAULT_OUTPUT_DIR),
    }

    if request.method == "POST":
        state["url"] = request.form.get("url", "").strip()
        state["output_dir"] = request.form.get("output_dir", "").strip()
        state["filename"] = request.form.get("filename", "").strip()
        state["browser"] = request.form.get("browser", "").strip()

        if not state["url"]:
            result["ok"] = False
            result["title"] = "Video URL is required"
            result["message"] = "Please provide a video URL."
        elif state["browser"] not in BROWSER_CHOICES:
            result["ok"] = False
            result["title"] = "Browser value is invalid"
            result["message"] = "Invalid browser option."
        elif state["filename"] and not sanitize_filename(state["filename"]):
            result["ok"] = False
            result["title"] = "File name is not usable"
            result["message"] = (
                "That file name contains only characters that cannot be used. "
                "Try letters, numbers, spaces, or dashes."
            )
        else:
            cmd = [sys.executable, str(SRC_DIR / "downloader.py"), state["url"]]

            if state["output_dir"]:
                cmd.extend(["--output-dir", state["output_dir"]])
            if state["filename"]:
                cmd.extend(["--filename", state["filename"]])
            if state["browser"]:
                cmd.extend(["--browser", state["browser"]])

            result["command"] = " ".join(cmd)
            ok, log = run_download_command(cmd)
            result = build_result_payload(
                ok=ok,
                browser=state["browser"],
                output_dir=state["output_dir"],
                log=log,
                command=result["command"],
            )

        if result["ok"] is False and not result["title"]:
            result["title"] = "Please review the form"
        if result["ok"] is False and not result["technical_note"]:
            result["technical_note"] = result["message"]

    return render_template(
        "index.html",
        state=state,
        result=result,
        browser_choices=BROWSER_CHOICES,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
