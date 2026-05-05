# Mattermost Backup & Viewer

A two-part tool for backing up Mattermost conversations and browsing them through a web interface — no database access required.

Inspired by [RobertKrajewski's Mattermost export script](https://gist.github.com/RobertKrajewski/5847ce49333062ea4be1a08f2913288c).

---

## Note
Due to the confidential nature of the data, it is strongly recommended that you secure access to the downloaded data, even on your local network!

---

## Features

- **Full backup** of all channels, direct messages, and group conversations you have access to
- **Attachment download** — images, videos, and files saved alongside messages
- **Web viewer** — browse backups in a chat-like interface served by Apache + PHP
- **Lazy loading** — channel messages are fetched on demand, not all at once
- **Virtual scroll** — handles channels with 100k+ messages without freezing the browser
- **Global search** — full-text search across all messages, server-side via PHP, results sorted newest-first
- **Inline media** — images and MP4 videos displayed directly in the conversation
- **Lightbox** — click any image to open it fullscreen
- **Pinned messages** — backed up and browsable via a dedicated tab
- **Grouped sidebar** — channels, group messages, and DMs in separate collapsible sections
- **Resizable sidebar** — drag the right edge to adjust width (saved across sessions)
- **Dark / Light mode** — toggle in the sidebar footer (saved across sessions)
- **Markdown tables** — rendered as HTML tables inline in messages
- **Auto-load** — no manual file picking; everything loads automatically on page open

---

## Requirements

### Backup script
- Python 3.8+
- [`mattermostdriver`](https://github.com/Vaelor/python-mattermost-driver)

### Viewer
- PHP 7+ (no extensions required)
- Apache2 (optional, see below)

---

## Installation

### 1. Clone the repository

```bash
cd $HOME
git clone https://github.com/lukaszmarcola/mattermost_backup
cd mattermost_backup
```

### 2. Set up Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install mattermostdriver
```

### 3. Create results directory

```bash
mkdir -p results
```

---

## Running the viewer

### Option A — PHP built-in server (simplest, no Apache needed)

No symlinks or extra configuration required.

**Configure `mattermost.php`:**

```php
define('RESULTS_URL', '/results');
```

**Start the server:**

```bash
cd ~/mattermost_backup
php -S localhost:8080 -t .
```

Open **`http://localhost:8080/mattermost.php`** in your browser.

> PHP serves files directly from `~/mattermost_backup/` so `results/` is reachable at `/results` with no extra setup.

---

### Option B — Apache2

**Install Apache and PHP if needed:**

```bash
sudo apt install apache2 php libapache2-mod-php
```

**Set up the directory structure:**

```bash
# Create the directory for the viewer under Apache's document root
sudo mkdir -p /var/www/html/mattermost

# Copy the viewer script
sudo cp mattermost.php /var/www/html/mattermost/

# Create a symlink so Apache can serve the backup files
sudo ln -s ~/mattermost_backup/results /var/www/html/mattermost/results

# Allow Apache to read your home directory
chmod o+x ~
```

Your final structure will look like this:

```
~/mattermost_backup/
├── mattermost_backup.py
├── mattermost.php
├── config.json               ← auto-generated on first run
├── venv/
└── results/

/var/www/html/mattermost/
├── mattermost.php
└── results -> ~/mattermost_backup/results    ← symlink
```

**Configure `mattermost.php`:**

```php
define('RESULTS_URL', '/mattermost/results');
```

**Enable symlinks in Apache (if needed):**

Add this to your site config (`/etc/apache2/sites-enabled/000-default.conf`):

```apache
<Directory /var/www/html/mattermost>
    Options +FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>
```

Then reload Apache:

```bash
sudo systemctl reload apache2
```

Open **`http://localhost/mattermost/mattermost.php`** in your browser.

---

## Running a backup

```bash
cd ~/mattermost_backup
source venv/bin/activate
python3 mattermost_backup.py
```

On first run you will be prompted for:
- Server address (without `https://`)
- Login mode: `password` or `token`
- Whether to download attachments
- Export format: `json`, `markdown`, or `both`

Settings (without password) are saved to `config.json` for subsequent runs.

**Command-line options:**

```bash
python3 mattermost_backup.py --format markdown         # override export format
python3 mattermost_backup.py --after 2024-01-01        # export posts after date
python3 mattermost_backup.py --before 2024-12-31       # export posts before date
python3 mattermost_backup.py --config my_config.json   # use custom config file
```

---

## Authentication

The backup script supports two login modes:

**Password login:**
```
Login mode: password
Username: your.username
Password: (hidden input)
```

**Token login** (e.g. GitLab OAuth):
```
Login mode: token
Token: your-MMAUTHTOKEN
```

On Windows, the script can automatically extract `MMAUTHTOKEN` from Firefox cookies.

---

## Viewer Features

### Browsing
- Sidebar lists all channels grouped into **Channels**, **Group messages**, and **Direct messages** — each section is collapsible
- **Resizable sidebar** — drag the right edge to adjust width (saved across sessions)
- Click a channel to load its messages
- Messages load newest-first (bottom of the page), scroll up to load older messages
- Messages are grouped by date with dividers
- Threaded replies are indented
- **Dark / Light mode** toggle in the sidebar footer (saved across sessions)

### Pinned messages
Each channel has a **📌 Pinned** tab showing only pinned messages. The badge displays the count. Pinned status is captured during backup via the Mattermost API.

### Search

| | Where | How |
|---|---|---|
| **Local search** | Current channel | Filter bar below the topbar — filters as you type |
| **Global search** | All channels | Search bar at the top — press Enter or click **Search** |

Global search is handled server-side by PHP so it is fast even across large archives. Results are sorted newest-first. Clicking a result opens the channel and pre-fills the local search.

### Media
- **Images** (png, jpg, jpeg, gif, webp, svg, bmp, tiff) — displayed inline, click to open lightbox
- **Videos** (mp4, webm, ogg, mov, mkv) — inline player with controls
- **Other files** — shown as a chip with filename

### Keyboard shortcuts

| Key | Action |
|---|---|
| `Escape` | Close lightbox / close global search results |
| `Enter` | Submit global search |

---

## Output Format

Each channel produces a folder named after the channel's display name, containing:

- `ChannelName.json` — full export with metadata and all messages
- `ChannelName.md` — human-readable Markdown (if `markdown` or `both` format selected)
- `0001_filename.ext` — downloaded attachments, prefixed with message index

**JSON structure:**
```json
{
  "channel": {
    "id": "...",
    "display_name": "general",
    "type": "O",
    "team": "my-team",
    "exported_at": "2026-05-04T13:00:00Z"
  },
  "posts": [
    {
      "idx": 0,
      "id": "...",
      "root_id": "",
      "created": "2023-01-15T09:23:11Z",
      "username": "john.doe",
      "message": "Hello!",
      "pinned": false,
      "files": ["0000_screenshot.png"]
    }
  ]
}
```

Channel types: `O` = public, `P` = private, `D` = direct message, `G` = group message.

---

## PHP Viewer API

`mattermost.php` doubles as a REST-like API when called with query parameters:

| Endpoint | Description |
|---|---|
| `mattermost.php` | Serves the HTML viewer |
| `mattermost.php?api` | Returns JSON index of all channels with metadata |
| `mattermost.php?search=query` | Full-text search, returns up to 50 results sorted newest-first |
| `mattermost.php?search=query&limit=100` | Full-text search with custom result limit (max 200) |

---

## License

MIT

---

[github.com/lukaszmarcola/mattermost_backup](https://github.com/lukaszmarcola/mattermost_backup)
