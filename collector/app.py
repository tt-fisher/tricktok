import re
import time
import sqlite3
from datetime import datetime
from flask import Flask, request, g, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "irgend_ein_schlüssel"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect("datenbank.db")
        # Keine UNIQUE-Konstraint, da wir manuell Duplikate prüfen
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kanal TEXT,
                zeitstempel TEXT,
                user_agent TEXT,
                ip_address TEXT,
                system_language TEXT
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

    # Gesamtanzahl Einträge ermitteln
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

    if request.method == "POST":
        letzte_zeit = session.get("last_submit_time", 0)
        aktuelle_zeit = time.time()

        # 10-Sekunden-Sperre für die gesamte Eingabe
        if aktuelle_zeit - letzte_zeit < 10:
            fehlermeldung = "Nur alle 10 Sekunden möglich"
            return render_template(
                "index.html",
                links=rows,
                fehlermeldung=fehlermeldung,
                total_links=total_links,
                page=page,
                per_page=per_page
            )

        # Mehrere Links in einer Textarea
        eingabe_text = request.form.get("eingabe_link", "").strip()
        lines = eingabe_text.split("\n")

        valid_found = False
        cursor = db.cursor()

        # Metadaten
        user_agent = request.headers.get("User-Agent", "Unbekannt")
        ip_address = request.remote_addr or "Unbekannt"
        system_language = request.headers.get("Accept-Language", "Unbekannt")

        for line in lines:
            kanal_name = extract_channel(line)
            if kanal_name:
                valid_found = True

                # Prüfen, ob kanal_name bereits existiert
                cursor.execute("SELECT 1 FROM links WHERE kanal = ? LIMIT 1", (kanal_name,))
                exists = cursor.fetchone()

                if not exists:
                    # Nur einfügen, wenn nicht vorhanden
                    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        """
                        INSERT INTO links (kanal, zeitstempel, user_agent, ip_address, system_language)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (kanal_name, zeit, user_agent, ip_address, system_language)
                    )

        if not valid_found:
            fehlermeldung = "Keine gültigen TikTok-Links gefunden"
            return render_template(
                "index.html",
                links=rows,
                fehlermeldung=fehlermeldung,
                total_links=total_links,
                page=page,
                per_page=per_page
            )

        # Änderungen übernehmen
        db.commit()

        # Sperrzeit aktualisieren
        session["last_submit_time"] = aktuelle_zeit

        return redirect(url_for("index"))

    return render_template(
        "index.html",
        links=rows,
        total_links=total_links,
        page=page,
        per_page=per_page
    )

if __name__ == "__main__":
    app.run(debug=True)