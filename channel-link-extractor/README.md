
# TikTok Channal-link-extractor

## Beschreibung

Ein TikTok-Crawler, der ausgewählte TikTok-Kanäle in definierten Intervallen verfolgt und Änderungen (neue Videos, Anzahl Kommentare, Views, Reposts und Likes) sowie neue Videodateien protokolliert. 

Dieser Crawler verarbeitet ausschließlich Videodateien und deren Metadaten. __TikTok-Fotos und deren Metadaten werden nicht verarbeitet.__

__________


## Installation

### Voraussetzungen

- Debian-basiertes System
- `yt-dlp` und `ffmpeg` müssen durch `apt-get` installiert werden
- Conda muss bereits installiert sein

### Installation

**Systempakete installieren**

Führe die folgenden Befehle aus, um die benötigten Pakete zu installieren:

`yt-dlp` wird im Python Skript als `subprocess`ausgeführt und muss auf dem System global installiert werden.

#### Systempakete aktualisieren:

    ```bash
    sudo apt-get update
    ```

 `yt-dlp` installieren:

    ```bash
    sudo apt-get install -y yt-dlp
    ```

 `ffmpeg` installieren (optional):

    ```bash
    sudo apt-get install -y ffmpeg
    ```

#### Conda-Umgebung erstellen**

 Erstelle eine Conda-Umgebung namens `sharedPython`:

    ```bash
    conda create -n sharedPython python=3.9
    ```

#### Aktiviere die neu erstellte Umgebung:

    ```bash
    conda activate sharedPython
    ```

#### Installiere die benötigten Python-Pakete:

    ```bash
    conda install -c conda-forge requests beautifulsoup4
    pip install tiktokpy
    ```

## Einrichtung mit systemd

Anstelle eines Cronjobs kannst du `systemd` verwenden, um das Skript regelmäßig auszuführen.

 Erstelle eine `systemd`-Service-Datei `/etc/systemd/system/tiktok-crawler.service`:

    ```ini
    [Unit]
    Description=TikTok Crawler Service

    [Service]
    Type=simple
    ExecStart=/bin/bash /home/user/tricktok/channel-link-extractor/run_script.sh
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target
    ```

 Erstelle eine `systemd`-Timer-Datei `/etc/systemd/system/tiktok-crawler.timer`:

    ```ini
    [Unit]
    Description=Run TikTok Crawler every 12 hours

    [Timer]
    OnBootSec=10min
    OnUnitActiveSec=12h
    Persistent=true

    [Install]
    WantedBy=timers.target
    ```

 Lade die `systemd`-Dienstdateien neu:

    ```bash
    sudo systemctl daemon-reload
    ```

 Aktiviere und starte den Timer:

    ```bash
    sudo systemctl enable tiktok-crawler.timer
    sudo systemctl start tiktok-crawler.timer
    ```

## Verwendung

Das Skript wird nun automatisch alle 12 Stunden durch `systemd` ausgeführt. Die Ausgaben und Protokolle können mit `journalctl` eingesehen werden:

```bash
journalctl -u tiktok-crawler.service
```


## Crawler-Skript


Dieses Skript dient dazu, Videodaten von TikTok zu sammeln und in einer Datenbank zu speichern. Es protokolliert Aktivitäten, erstellt oder öffnet eine Datenbank, in der es die Metadaten der Videos sowie deren Metriken speichert. 

_________

### Logging verfolgen

```
tail -f metadata_extraction1.log
```


```bash
import os
import sqlite3
import subprocess
import json
import logging
from datetime import datetime

# Logging 
logging.basicConfig(
    filename='metadata_extraction1.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("Skript gestartet")

# SQLite-Datenbank erstellen
def init_db(db_name="media_metadata1.db"):
    logging.debug(f"Initialisiere Datenbank: {db_name}")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # Haupttabelle 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media_metadata (
            id TEXT PRIMARY KEY,
            url TEXT,
            title TEXT,
            description TEXT,
            duration INTEGER,
            uploader TEXT,
            uploader_id TEXT,
            channel TEXT,
            channel_id TEXT,
            channel_url TEXT,
            track TEXT,
            album TEXT,
            artists TEXT,
            timestamp INTEGER,
            extractor TEXT
        )
    ''')
    # Tabelle für die Historie der Metriken
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media_metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            view_count INTEGER,
            like_count INTEGER,
            repost_count INTEGER,
            comment_count INTEGER,
            timestamp INTEGER,
            FOREIGN KEY(video_id) REFERENCES media_metadata(id)
        )
    ''')
    conn.commit()
    logging.debug("Datenbank initialisiert")
    return conn

# Metadaten extrahieren mit yt-dlp
def extract_metadata(url):
    logging.debug(f"Extrahiere Metadaten für URL: {url}")
    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-single-json", url],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logging.debug(f"Metadaten erfolgreich extrahiert für URL: {url}")
            return json.loads(result.stdout)
        else:
            logging.error(f"Fehler beim Abrufen von {url}: {result.stderr}")
            return None
    except Exception as e:
        logging.error(f"Fehler beim Abrufen von {url}: {e}")
        return None

# Video-Metadaten in SQLite speichern
def save_video_metadata(conn, video):
    cursor = conn.cursor()
    try:
        # Speichern 
        cursor.execute('''
            INSERT OR REPLACE INTO media_metadata (
                id, url, title, description, duration,
                uploader, uploader_id, channel, channel_id,
                channel_url, track, album, artists, timestamp, extractor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            video.get("id"),
            video.get("url"),
            video.get("title"),
            video.get("description"),
            video.get("duration"),
            video.get("uploader"),
            video.get("uploader_id"),
            video.get("channel"),
            video.get("channel_id"),
            video.get("channel_url"),
            video.get("track"),
            video.get("album"),
            ", ".join(video.get("artists", [])),
            video.get("timestamp"),
            video.get("extractor")
        ))
        
        # Speichern der Metriken in der Historientabelle
        cursor.execute('''
            INSERT INTO media_metrics_history (
                video_id, view_count, like_count, repost_count, comment_count, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            video.get("id"),
            video.get("view_count"),
            video.get("like_count"),
            video.get("repost_count"),
            video.get("comment_count"),
            int(datetime.now().timestamp())
        ))
        
        conn.commit()
        logging.debug(f"Metadaten und Metriken für Video ID={video.get('id')} gespeichert")
    except sqlite3.Error as e:
        logging.error(f"SQLite-Fehler bei Video ID={video.get('id')}: {e}")

# Playlist-Metadaten speichern
def process_playlist_metadata(conn, playlist_metadata):
    if not playlist_metadata or "entries" not in playlist_metadata:
        logging.debug("Keine Videos in der Playlist gefunden")
        return

    for video in playlist_metadata["entries"]:
        save_video_metadata(conn, video)

# Links lesen und verarbeiten
def process_links(file_name="links.txt", db_name="media_metadata1.db"):
    logging.debug(f"Beginne Verarbeitung von Links aus Datei: {file_name}")
    conn = init_db(db_name)
    if not os.path.exists(file_name):
        logging.error(f"Datei {file_name} nicht gefunden")
        return

    with open(file_name, "r") as file:
        links = [line.strip() for line in file if line.strip()]

    logging.debug(f"Gefundene Links: {links}")

    for url in links:
        logging.info(f"Verarbeite URL: {url}")
        playlist_metadata = extract_metadata(url)
        if playlist_metadata:
            process_playlist_metadata(conn, playlist_metadata)
        else:
            logging.warning(f"Keine Metadaten gefunden für URL: {url}")

    conn.close()
    logging.debug("Verarbeitung abgeschlossen")

if __name__ == "__main__":
    process_links()
```

