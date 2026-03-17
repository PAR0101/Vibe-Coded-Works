# YTMusicPlayer 🎵

A premium YouTube Music desktop player with a **dark glassmorphism + lava lamp** aesthetic.  
Built in Python with PyQt5 and yt-dlp — streams audio directly, no downloads.

```
┌──────────────────────────────────────────────────────────────┐
│  🌊 Animated lava-lamp background (blobs, slow motion)        │
│  ┌──────────┬────────────────────────────────────────────┐   │
│  │ Sidebar  │  Content Panel                             │   │
│  │          │  ┌─────────────────────────────────────┐  │   │
│  │ 🔍 Search│  │  🔍 Search bar                       │  │   │
│  │ 🏠 Home  │  │  ─────────────────────────────────── │  │   │
│  │ ♥  Liked │  │  Track list (title, artist, duration)│  │   │
│  │ 🕐 Hist. │  │                                      │  │   │
│  │ 📋 PL 1  │  └─────────────────────────────────────┘  │   │
│  │ 📋 PL 2  │                                            │   │
│  └──────────┴────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [Thumb] Title · Artist  ⏮ ▶ ⏭ ⏹  ━━●━━  🔊──┤  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## Features

### 🎧 Audio Streaming
- Streams audio **directly from YouTube** via yt-dlp (best-quality audio-only)
- **No files downloaded** — pure adaptive streaming
- Resolves and caches stream URLs for fast playback
- Supports any public YouTube URL (video, playlist, channel)

### 🔍 Search
- Full-text search: songs, artists, albums, playlists
- 25 results per search with thumbnails and duration
- Animated placeholder hints while idle

### ▶ Playback Controls
| Control | Action |
|---------|--------|
| Play/Pause | Big gradient button + `Space` |
| Previous | `⏮` or `Ctrl+←` (restarts if > 3 s in) |
| Next | `⏭` or `Ctrl+→` |
| Stop | `⏹` |
| Seek | Click/drag progress bar |
| Volume | Slider + `Ctrl+↑/↓` |

### 📚 Library
- **Liked Songs** — like/unlike with `♥` or `Ctrl+L`
- **History** — last 200 played tracks, auto-saved
- **Playlists** — create, rename, delete; add tracks via context menu
- All data stored in `~/.ytmusicplayer/` as JSON

### 🔐 YouTube Account Login (Optional)
- Connect your account via exported browser cookies (`cookies.txt`)
- Unlocks: Liked Videos, Watch History, personal recommendations
- Session persisted across launches; cookies never stored on external servers

### 🎨 UI / UX
- **Dark glassmorphism**: frosted-glass panels, subtle borders, soft shadows
- **Lava lamp background**: 7 morphing blobs in purple/pink/blue/red, 30 fps
- Smooth hover transitions on all buttons
- Right-click context menu on tracks: Play, Queue, Like, Add to Playlist
- Resizable window, scroll areas with custom slim scrollbars
- Status bar and menu bar

---

## Quick Start

### 1. Install dependencies

```bash
pip install PyQt5 yt-dlp requests Pillow
```

### 2. Run

```bash
python main.py
# or, auto-install on first run:
python setup_and_run.py
```

### System requirements
- Python 3.10+
- Windows / macOS / Linux (any desktop with Qt5 support)
- Internet connection (for streaming)

---

## Connecting Your YouTube Account

To access your **Liked Songs**, **Watch History**, and personalized content:

1. Install the **cookies.txt** browser extension:
   - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
   - Chrome: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/)

2. Visit [youtube.com](https://youtube.com) while logged in

3. Click the extension → **Export cookies for youtube.com**

4. Save as `cookies.txt` anywhere on your machine

5. In YTMusicPlayer: **File → Connect YouTube Account** → Browse to the file

Your session will be remembered across launches.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space` | Play / Pause |
| `Ctrl+→` | Next track |
| `Ctrl+←` | Previous track |
| `Ctrl+F` | Focus search bar |
| `Ctrl+↑` | Volume up |
| `Ctrl+↓` | Volume down |
| `Ctrl+L` | Like current track |
| `Ctrl+N` | New playlist |
| `Ctrl+Q` | Quit |

---

## Project Structure

```
ytmusic_player/
├── main.py                  # Entry point
├── setup_and_run.py         # Auto-install + launch
├── requirements.txt
│
├── core/
│   ├── audio_engine.py      # yt-dlp streaming + QMediaPlayer playback
│   ├── library.py           # Local library: playlists, liked, history
│   └── yt_fetcher.py        # Async YouTube URL / playlist fetcher
│
└── ui/
    ├── main_window.py        # Top-level window, all wiring
    ├── lava_lamp.py          # Animated lava-lamp background widget
    ├── theme.py              # Colors, fonts, full Qt stylesheet
    ├── sidebar.py            # Navigation sidebar
    ├── content_panel.py      # Search bar + section header + track list
    ├── player_bar.py         # Transport controls, progress, volume
    ├── track_list.py         # Scrollable track rows with thumbnails
    └── login_dialog.py       # YouTube cookie-based login dialog
```

---

## Architecture Notes

### Audio pipeline
```
User picks track
    → AudioEngine.load_and_play(TrackInfo)
    → Background thread: yt-dlp extracts best-audio stream URL
    → QMediaPlayer.setMedia(QUrl(stream_url))
    → QMediaPlayer streams and decodes natively
    → Signals: position_changed, duration_changed → PlayerBar
```

### Lava lamp rendering
```
QTimer @ 30 fps → Blob.update() for each blob
    → QPainter with CompositionMode_Plus (additive blending)
    → Radial gradients per blob
    → Vignette overlay to darken edges
```

### Thread safety
All yt-dlp work runs in daemon threads.  
Results are delivered back to the Qt main thread via `QMetaObject.invokeMethod` with `QueuedConnection` or via `pyqtSignal`.

---

## Customisation

Edit `ui/theme.py` to change:
- `ACCENT_PURPLE / ACCENT_PINK / ACCENT_BLUE` — button and progress bar accent colors
- `GLASS_BG / GLASS_BORDER` — panel transparency

Edit `ui/lava_lamp.py` to change:
- `Blob.COLORS` — blob color palette
- `LavaLampWidget.N_BLOBS` — number of blobs
- `LavaLampWidget.FPS` — animation frame rate (lower = less CPU)
- `Blob.base_r` range — blob size

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No module named PyQt5` | `pip install PyQt5` |
| `No module named yt_dlp` | `pip install yt-dlp` |
| Stream fails / no audio | Update yt-dlp: `pip install -U yt-dlp` |
| Login fails | Re-export cookies (they expire); try a different browser |
| Black window on Linux | Try `QT_QPA_PLATFORM=xcb python main.py` |
| Slow thumbnails | Normal on first load; they cache after that |

---

## License

MIT — free to use, modify, and distribute.  
YouTube content is subject to YouTube's Terms of Service.
