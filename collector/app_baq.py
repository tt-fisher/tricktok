import re
import time
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, g, render_template, redirect, url_for

# Logging-Konfiguration
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

app = Flask(__name__)
app.secret_key = "irgend_ein_schlüssel"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        # Verbindung über verschlüsselten Socket oder abgesicherten Tunnel realisieren (je nach Umgebung).
        db = g._database = sqlite3.connect("datenbank.db")

        # Tabelle für Links mit Zeitstempel, Kanal, User-Agent, IP
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kanal TEXT,
                zeitstempel TEXT,
                user_agent TEXT,
                ip_address TEXT
            )
            """
        )

        # Neue Tabelle für IP-basierten Cooldown
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS ip_cooldowns (
                ip TEXT PRIMARY KEY,
                last_submit REAL
            )
            """
        )
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def extract_channel(link):
    """
    Extrahiert den Kanalnamen aus einem TikTok-Link.
    Beispiele:
      - https://www.tiktok.com/@meinKanal/video/12345 -> meinKanal
      - tiktok.com/@test123 -> test123
    """
    pattern = r"(?:https?:\/\/)?(?:www\.)?tiktok\.com\/@([^\/]+)"
    match = re.search(pattern, link.strip())
    if match:
        return match.group(1)
    return None

@app.route("/", methods=["GET", "POST"])
def index():
    db = get_db()

    # Paginierung
    page = int(request.args.get("page", 1))
    per_page = 50
    offset = (page - 1) * per_page

    # Gesamtanzahl Einträge
    total_links = db.execute("SELECT COUNT(*) FROM links").fetchone()[0]

    # Jüngste Einträge zuerst (id DESC)
    rows = db.execute(
        """
        SELECT kanal, zeitstempel
        FROM links
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (per_page, offset)
    ).fetchall()

    fehlermeldung = None

    if request.method == "POST":
        ip_address = request.remote_addr or "Unbekannt"
        aktuelle_zeit = time.time()

        cursor = db.cursor()

        # IP-spezifische Sperre prüfen
        result = cursor.execute(
            "SELECT last_submit FROM ip_cooldowns WHERE ip = ?",
            (ip_address,)
        ).fetchone()

        if result:
            letzte_zeit = result[0]
            if aktuelle_zeit - letzte_zeit < 10:
                fehlermeldung = "Nur alle 10 Sekunden möglich"
                logging.info(
                    "Abgewiesen: IP %s hat zu schnell hintereinander gepostet.",
                    ip_address
                )
                return render_template(
                    "index.html",
                    links=rows,
                    fehlermeldung=fehlermeldung,
                    total_links=total_links,
                    page=page,
                    per_page=per_page
                )

        eingabe_text = request.form.get("eingabe_link", "").strip()
        kanal_name = extract_channel(eingabe_text)

        if not kanal_name:
            fehlermeldung = "Keine gültige TikTok-URL gefunden"
            logging.info("Ungültiger Link eingegeben: %s", eingabe_text)
            return render_template(
                "index.html",
                links=rows,
                fehlermeldung=fehlermeldung,
                total_links=total_links,
                page=page,
                per_page=per_page
            )

        # Kanal in Datenbank prüfen
        cursor.execute(
            "SELECT zeitstempel FROM links WHERE kanal = ? LIMIT 1", 
            (kanal_name,)
        )
        duplikat = cursor.fetchone()

        if duplikat:
            # Duplikat-Hinweis mit Datum
            vorhandenes_datum = duplikat[0]
            fehlermeldung = f"Kanal bereits vorhanden. Zuletzt gespeichert am {vorhandenes_datum}"
            logging.info("Kanal bereits vorhanden: %s (IP: %s)", kanal_name, ip_address)

            # IP-Cooldown aktualisieren (auch wenn Duplikat)
            cursor.execute(
                "INSERT OR REPLACE INTO ip_cooldowns (ip, last_submit) VALUES (?, ?)",
                (ip_address, aktuelle_zeit)
            )
            db.commit()

            return render_template(
                "index.html",
                links=rows,
                fehlermeldung=fehlermeldung,
                total_links=total_links,
                page=page,
                per_page=per_page
            )
        else:
            zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_agent = request.headers.get("User-Agent", "Unbekannt")

            cursor.execute(
                """
                INSERT INTO links (
                    kanal,
                    zeitstempel,
                    user_agent,
                    ip_address
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    kanal_name,
                    zeit,
                    user_agent,
                    ip_address
                )
            )
            db.commit()
            logging.info("Neuer Kanal gespeichert: %s (IP: %s)", kanal_name, ip_address)

            # IP-Cooldown aktualisieren oder anlegen
            cursor.execute(
                """
                INSERT OR REPLACE INTO ip_cooldowns (ip, last_submit)
                VALUES (?, ?)
                """,
                (ip_address, aktuelle_zeit)
            )
            db.commit()

        return redirect(url_for("index"))

    return render_template(
        "index.html",
        links=rows,
        fehlermeldung=fehlermeldung,
        total_links=total_links,
        page=page,
        per_page=per_page
    )

@app.route("/info")
def info():
    return render_template("info.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    app.run(debug=True)
