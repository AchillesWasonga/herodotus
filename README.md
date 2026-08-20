# mp4mp3dloader

Internal video downloader for YouTube, Instagram, and hundreds of other platforms supported by yt-dlp.

## Features
- Downloads highest available quality MP4
- Supports YouTube, Instagram, and any other site yt-dlp can extract from
- Saves metadata as `<title>.json` (description, uploader, upload date, etc.)
- Optional browser-cookie fallback for sources that require a logged-in session

## Web App (Recommended)
1. Install dependencies after activating python virtual environment:
`./.venv/bin/pip install -r requirements.txt`
2. Start server:
`python src/web_app.py`
3. Open:
`http://127.0.0.1:5050`
4. Paste a URL, choose a destination folder, and click **Start Download**.

Note: `GET /favicon.ico 404` in Flask logs is harmless.
If a source fails with access/login warnings, set **Browser Cookies** to a logged-in browser (e.g., `safari` or `chrome`).
