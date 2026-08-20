import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import yt_dlp


BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / "downloads"

BROWSER_CHOICES = ["safari", "chrome", "firefox", "edge", "brave", "chromium"]

LOGIN_REQUIRED_SIGNALS = [
    "login required",
    "requested content is not available",
    "rate-limit reached",
    "main webpage is locked behind the login page",
    "unable to extract shared data",
    "unable to extract additional data",
    "is not granting access",
    "empty media response",
    "check if this post is accessible in your browser",
    "sign in to confirm",
    "private video",
]


def ensure_dependencies() -> None:
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg is not installed or not on PATH.")
        print("Install it with: brew install ffmpeg")
        sys.exit(1)


def resolve_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir is None:
        return DOWNLOADS_DIR

    output_dir = Path(raw_output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    return output_dir.resolve()


def build_options(output_dir: Path, browser: str | None) -> dict:
    output_template = str(output_dir / "%(uploader|unknown_creator)s - %(title)s.%(ext)s")
    opts = {
        "format": "bv*+ba/b",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }
    if browser:
        opts["cookiesfrombrowser"] = (browser, None, None, None)
    return opts


def should_retry_with_cookies(message: str) -> bool:
    lowered = message.lower()
    return any(signal in lowered for signal in LOGIN_REQUIRED_SIGNALS)


def cookies_help_message(browser: str | None) -> str:
    if browser:
        return (
            f"This source blocked public access even with {browser} cookies. "
            "Try a different browser or confirm that browser is logged in."
        )
    return (
        "This source requires a logged-in session. Retry with --browser "
        "{safari,chrome,firefox,edge,brave,chromium} using a browser that is logged in."
    )


def find_final_output_path(
    info: dict,
    ydl: yt_dlp.YoutubeDL,
    output_dir: Path,
    started_at: float,
) -> Path | None:
    expected_suffix = ".mp4"
    candidates: list[Path] = []

    def add_candidate(path_value: str | None) -> None:
        if not path_value:
            return
        candidate = Path(path_value).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        candidates.append(candidate)

    add_candidate(info.get("filepath"))
    add_candidate(info.get("_filename"))

    for item in info.get("requested_downloads") or []:
        add_candidate(item.get("filepath"))
    for item in info.get("requested_formats") or []:
        add_candidate(item.get("filepath"))

    prepared = ydl.prepare_filename(info)
    add_candidate(prepared)
    add_candidate(str(Path(prepared).with_suffix(".mp4")))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matching_files = sorted(
        output_dir.glob(f"*{expected_suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for match in matching_files:
        if match.stat().st_mtime >= started_at - 5:
            return match

    return matching_files[0] if matching_files else None


def build_video_metadata(info: dict, source_url: str, final_path: Path | None) -> dict:
    metadata = {
        "source_url": source_url,
        "id": info.get("id"),
        "title": info.get("title"),
        "description": info.get("description"),
        "uploader": info.get("uploader"),
        "uploader_id": info.get("uploader_id"),
        "channel": info.get("channel"),
        "channel_id": info.get("channel_id"),
        "upload_date": info.get("upload_date"),
        "timestamp": info.get("timestamp"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
        "extractor": info.get("extractor"),
        "extractor_key": info.get("extractor_key"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "tags": info.get("tags"),
        "categories": info.get("categories"),
        "width": info.get("width"),
        "height": info.get("height"),
        "fps": info.get("fps"),
        "media_path": str(final_path) if final_path is not None else None,
    }
    return metadata


def save_video_metadata(metadata: dict, output_dir: Path, final_path: Path | None) -> Path:
    if final_path is not None:
        metadata_path = final_path.with_suffix(".json")
    else:
        fallback_name = metadata.get("id") or "video_metadata"
        metadata_path = output_dir / f"{fallback_name}.json"

    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return metadata_path


def extract_and_download(url: str, output_dir: Path, browser: str | None) -> tuple[dict, yt_dlp.YoutubeDL]:
    opts = build_options(output_dir, browser)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info, ydl


def download_media(url: str, output_dir: Path, browser: str | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.time()

    print(f"Starting download: {url}")
    print(f"Output directory: {output_dir}")

    try:
        info, ydl = extract_and_download(url, output_dir, None)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        if not should_retry_with_cookies(message):
            print(f"Download failed: {exc}")
            sys.exit(1)
        if not browser:
            print(f"Download failed: {cookies_help_message(browser)}")
            sys.exit(1)
        print(f"Public access blocked, retrying with {browser} cookies...")
        try:
            info, ydl = extract_and_download(url, output_dir, browser)
        except yt_dlp.utils.DownloadError as retry_exc:
            print(f"Download failed: {retry_exc}")
            sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        sys.exit(1)

    print("Done.")

    if isinstance(info, dict):
        final_path = find_final_output_path(info, ydl, output_dir, started_at)
        metadata = build_video_metadata(info, url, final_path)
        metadata_path = save_video_metadata(metadata, output_dir, final_path)
    else:
        final_path = None
        metadata_path = None

    if final_path is not None:
        print(f"Saved file: {final_path}")
    else:
        print(f"Saved file in directory: {output_dir}")

    if metadata_path is not None:
        print(f"Metadata saved: {metadata_path}")


def main() -> None:
    ensure_dependencies()

    parser = argparse.ArgumentParser(
        description="Download a video URL (YouTube, Instagram, and hundreds of other sites via yt-dlp) as MP4"
    )
    parser.add_argument("url", help="Video URL")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for downloaded media",
    )
    parser.add_argument(
        "--browser",
        choices=BROWSER_CHOICES,
        default=None,
        help="Optional browser to load cookies from if the source requires a logged-in session",
    )

    args = parser.parse_args()
    output_dir = resolve_output_dir(args.output_dir)

    download_media(args.url, output_dir, browser=args.browser)


if __name__ == "__main__":
    main()
