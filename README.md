# mp4mp3dloader

An internal video downloader for YouTube, Instagram, and the hundreds of other
sites supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp). Paste a link,
pick where it should land, and get the highest-quality MP4 saved locally —
without ad-filled third-party downloader websites.

---

## What it does

- **Downloads from any yt-dlp-supported site.** YouTube, YouTube Shorts,
  Instagram Reels, TikTok, X/Twitter, Facebook, Vimeo, and many more. There is
  no platform dropdown — the extractor is chosen from the URL automatically.
- **Grabs the best quality available.** Downloads the best video and best audio
  stream separately, then merges them into a single MP4 with ffmpeg.
- **Saves metadata alongside each video.** Every download writes a `.json`
  sidecar next to the MP4 with the title, description, uploader, upload date,
  duration, view/like counts, and source URL.
- **Handles login-walled sources.** If a site refuses anonymous access, the
  download can be retried using cookies from a browser you are already logged
  into.
- **Never overwrites or silently skips.** Default filenames include the video
  ID, so multiple posts from the same account cannot collide. If you supply
  your own name and it is taken, the new file becomes `Name (2).mp4`.

### Two ways to use it

| | Web app | Command line |
|---|---|---|
| Best for | Everyday use | Scripting and batch loops |
| Entry point | `src/web_app.py` | `src/downloader.py` |

Both run the same download logic — the web app simply shells out to the CLI and
formats the result.

---

## Requirements

- **Python 3.12 or 3.13**
- **ffmpeg**, on your `PATH` (used to merge video and audio)

Install ffmpeg on macOS with Homebrew:

```bash
brew install ffmpeg
```

> **Note for this machine:** Homebrew's Python 3.14 has a broken `pyexpat`
> module (a libexpat symbol mismatch) that makes `pip` and virtual environment
> creation fail. Use `python3.13` explicitly, as shown below.

---

## Installation

From the project root:

```bash
# 1. Create a virtual environment
python3.13 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

Your prompt will show `(.venv)` once the environment is active. Run
`deactivate` to leave it.

### Keeping yt-dlp current

Video sites change their internals often, and an outdated yt-dlp is the single
most common cause of a download failing with `HTTP Error 403` or a
format-not-found error. If a download starts failing for no obvious reason,
update first:

```bash
pip install -U yt-dlp
```

Restart the server afterwards so the running process picks up the new version.

---

## Running

### Web app (recommended)

```bash
source .venv/bin/activate
python src/web_app.py
```

Then open **<http://127.0.0.1:5050>**.

Fill in the form and click **Start Download**:

| Field | Required | Notes |
|---|---|---|
| **Video URL** | Yes | Any supported video link. |
| **Browser Cookies** | No | Pick a browser you are logged into if the site blocks anonymous access. |
| **Destination Folder** | No | An absolute path works best. Created automatically if missing. |
| **File Name** | No | Leave blank to name it automatically. Do not add `.mp4`. |

The page waits while the download runs, then shows the saved paths, or a plain
explanation plus the full log if something failed.

> `GET /favicon.ico 404` in the Flask logs is harmless.
>
> If you see `Address already in use`, an old server is still running. Stop it
> with `lsof -ti:5050 | xargs kill`.

### Command line

```bash
source .venv/bin/activate
python src/downloader.py "<url>" [options]
```

| Option | Description |
|---|---|
| `--output-dir PATH` | Where to save. Defaults to `downloads/` in the project root. |
| `--filename NAME` | Name for the saved file. The extension is added for you. |
| `--browser NAME` | Load cookies from `safari`, `chrome`, `firefox`, `edge`, `brave`, or `chromium`. |
| `-h`, `--help` | Show all options. |

Examples:

```bash
# Simplest form — saves to downloads/
python src/downloader.py "https://www.youtube.com/watch?v=..."

# Choose a folder and a name
python src/downloader.py "https://www.instagram.com/reel/..." \
  --output-dir ~/Desktop/clips \
  --filename "Match Highlight"

# Use a logged-in Safari session for a restricted post
python src/downloader.py "https://www.instagram.com/reel/..." --browser safari
```

---

## How files are named

**Without** a `--filename`, downloads are named:

```
<Uploader> - <Title> [<id>].mp4
```

The trailing ID matters. Instagram titles nearly every reel from an account
identically (`Video by <handle>`), so without a unique ID the second and third
reels from the same page would resolve to a filename that already exists and be
skipped as already-downloaded. The ID makes every filename unique.

**With** a `--filename`, the name is used exactly as given, after:

- illegal characters (`< > : " / \ | ? *` and control characters) become `_`
- a trailing `.mp4` you typed is removed, so you never get `name.mp4.mp4`
- runs of whitespace collapse, and leading/trailing dots are stripped
- the result is truncated to 150 characters
- a name already in use gains a counter: `Name (2)`, `Name (3)`, …

Because path separators are stripped rather than honoured, a filename can never
write outside the destination folder. If a name reduces to nothing after
cleaning (for example `...`), it is rejected before any download starts.

The `.json` metadata sidecar always follows whatever name the video receives.

---

## Customization

Nearly everything worth adjusting is a named constant near the top of
[`src/downloader.py`](src/downloader.py) or
[`src/web_app.py`](src/web_app.py).

### Change the default download folder

`DOWNLOADS_DIR` in [`src/downloader.py`](src/downloader.py) and
`DEFAULT_OUTPUT_DIR` in [`src/web_app.py`](src/web_app.py) both point at
`downloads/`. Repoint them at, say, your Desktop:

```python
DOWNLOADS_DIR = Path.home() / "Desktop" / "clips"
```

### Change the port or expose the server

The last line of [`src/web_app.py`](src/web_app.py):

```python
app.run(host="127.0.0.1", port=5050, debug=True)
```

Change `port` if 5050 is taken. `host="127.0.0.1"` deliberately restricts access
to this machine — see the security note below before widening it.

### Change quality or output format

The `"format"` key in `build_options()` uses yt-dlp's
[format selection syntax](https://github.com/yt-dlp/yt-dlp#format-selection):

```python
"format": "bv*+ba/b",   # best video + best audio, falling back to best single file
```

Useful variations:

| Goal | Value |
|---|---|
| Cap resolution at 1080p | `"bv*[height<=1080]+ba/b[height<=1080]"` |
| Prefer smaller files | `"worstvideo+worstaudio/worst"` |
| Audio only | `"ba/b"` — also set `merge_output_format` and add a postprocessor to get MP3 |

### Change the automatic filename pattern

In `build_options()`, the no-custom-name branch:

```python
output_dir / "%(uploader|unknown_creator)s - %(title)s [%(id)s].%(ext)s"
```

Any [yt-dlp output template](https://github.com/yt-dlp/yt-dlp#output-template)
field works — for example `%(upload_date)s` to prefix the date. **Keep
`%(id)s`** unless you are certain your sources produce unique titles, or you
will reintroduce the filename-collision problem described above.

### Other knobs

| Constant | File | Purpose |
|---|---|---|
| `MAX_FILENAME_LENGTH` | `downloader.py` | Filename truncation limit (150). |
| `INVALID_FILENAME_CHARS` | `downloader.py` | Characters replaced with `_`. |
| `BROWSER_CHOICES` | both | Browsers offered for cookie loading. |
| `LOGIN_REQUIRED_SIGNALS` | `downloader.py` | Error phrases that trigger the cookie retry. |

To improve an unhelpful error message, edit `build_result_payload()` in
[`src/web_app.py`](src/web_app.py) — it matches phrases in the download log and
maps them to a title, a plain-language message, and suggested fixes.

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `HTTP Error 403` or no formats found | Outdated yt-dlp. Run `pip install -U yt-dlp` and restart the server. |
| **Login required** | Set **Browser Cookies** to a browser already logged into that site. |
| Downloaded video has no sound | Usually a restricted stream served to anonymous users. Retry with browser cookies. Verify with `ffprobe -v error -show_entries stream=codec_type -of csv=p=0 file.mp4` — you should see both `video` and `audio`. |
| `ffmpeg is missing` | `brew install ffmpeg`. |
| `Address already in use` | `lsof -ti:5050 \| xargs kill` |
| Second video from an account won't download | Should no longer happen. If it does, confirm the filename template still contains `%(id)s`. |
| `ensurepip` / `pyexpat` errors on setup | Homebrew Python 3.14 is broken here — build the venv with `python3.13`. |

---

## Project layout

```
mp4mp3dloader/
├── README.md              # This file
├── LICENSE                # MIT
├── requirements.txt       # yt-dlp + Flask
└── src/
    ├── downloader.py      # Download logic and CLI entry point
    ├── web_app.py         # Flask server, form handling, error messaging
    └── templates/
        └── index.html     # Single-page UI
```

---

## Notes and limits

- **Local and single-user.** The server binds to `127.0.0.1` and has no
  authentication. It also passes a filesystem path straight from the form to
  the downloader, so do not expose it on a shared network or the public
  internet without adding authentication and path restrictions first.
- **Debug mode is on**, which is convenient locally but must be turned off
  before running anywhere untrusted.
- **One download at a time.** The request blocks until the download finishes;
  a very long video will hold the page open.
- **Cookie loading reads your browser profile** to reach content your account
  can see. Nothing is uploaded anywhere, but it does mean the download acts as
  your logged-in account.
- **Downloading is not the same as having rights to reuse.** Reposting or
  redistributing what you download is subject to platform terms and copyright.
  The MIT license below covers *this tool's source code only* — it grants no
  rights over any media you download with it.

---

## License

Released under the [MIT License](LICENSE) — © 2026 Allan Wasonga. You are free
to use, modify, and redistribute this code, including commercially, provided
the copyright notice and license text are retained.

This project depends on, but does not bundle, two separately licensed projects:

| Dependency | License |
|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense (public domain) |
| [Flask](https://flask.palletsprojects.com/) | BSD-3-Clause |

`ffmpeg` is invoked as an external program rather than linked, and is licensed
separately (LGPL or GPL depending on how your build was compiled).
