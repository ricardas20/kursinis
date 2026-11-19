# -*- coding: utf-8 -*-
"""Filmų apžvalgos informacinės sistemos prototipas.

Duomenų schema atitinka kursinio darbo fizinį modelį.
Darbuotojo lentelė papildyta stulpeliu slaptazodis – jis reikalingas prisijungimui.
"""

import hashlib
import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE / "filmu_apzvalgos.db"))

app = Flask(__name__)
app.secret_key = "filmu-apzvalgos-kursinis"

PAREIGOS = (
    "Klientų aptarnavimo specialistas",
    "Apžvalgų moderatorius",
    "Marketingo vadybininkas",
)
BUSENOS = ("laukia moderavimo", "patvirtinta", "atmesta")


def slaptazodis(tekstas):
    return hashlib.sha256(tekstas.encode("utf-8")).hexdigest()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "darbuotojo_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def roles(*leidziamos):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "darbuotojo_id" not in session:
                return redirect(url_for("login"))
            if session.get("pareigos") not in leidziamos:
                flash("Šiai funkcijai jūsų pareigybė neturi teisių.")
                return redirect(url_for("filmai"))
            return fn(*args, **kwargs)

        return wrapper

    return deco


def perskaiciuoti_reitinga(conn, filmo_id):
    row = conn.execute(
        """
        SELECT ROUND(AVG(balas), 2) AS vidurkis
        FROM apzvalga
        WHERE filmo_id = ? AND busena = 'patvirtinta'
        """,
        (filmo_id,),
    ).fetchone()
    conn.execute(
        "UPDATE filmas SET reitingas = ? WHERE filmo_id = ?",
        (row["vidurkis"], filmo_id),
    )


def init_db():
    if DB_PATH.exists():
        return
    conn = db()
    conn.executescript(
        """
        CREATE TABLE zanras (
            zanro_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pavadinimas TEXT NOT NULL UNIQUE
        );
        CREATE TABLE filmas (
            filmo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pavadinimas TEXT NOT NULL,
            rezisierius TEXT NOT NULL,
            isleidimo_metai INTEGER NOT NULL CHECK (isleidimo_metai BETWEEN 1888 AND 2100),
            trukme_min INTEGER NOT NULL CHECK (trukme_min > 0),
            reitingas REAL CHECK (reitingas IS NULL OR (reitingas BETWEEN 1 AND 10)),
            zanro_id INTEGER NOT NULL REFERENCES zanras (zanro_id)
        );
        CREATE TABLE ziurovas (
            ziurovo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            naudotojo_vardas TEXT NOT NULL UNIQUE,
            vardas TEXT NOT NULL,
            pavarde TEXT NOT NULL,
            el_pastas TEXT NOT NULL UNIQUE
        );
        CREATE TABLE darbuotojas (
            darbuotojo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vardas TEXT NOT NULL,
            pavarde TEXT NOT NULL,
            pareigos TEXT NOT NULL CHECK (pareigos IN (
                'Klientų aptarnavimo specialistas',
                'Apžvalgų moderatorius',
                'Marketingo vadybininkas'
            )),
            prisijungimo_vardas TEXT NOT NULL UNIQUE,
            el_pastas TEXT NOT NULL,
            slaptazodis TEXT NOT NULL
        );
        CREATE TABLE apzvalga (
            apzvalgos_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tekstas TEXT NOT NULL,
            balas INTEGER NOT NULL CHECK (balas BETWEEN 1 AND 10),
            pateikimo_data TEXT NOT NULL,
            busena TEXT NOT NULL CHECK (busena IN ('laukia moderavimo', 'patvirtinta', 'atmesta')),
            moderatoriaus_pastabos TEXT,
            publikavimo_data TEXT,
            filmo_id INTEGER NOT NULL REFERENCES filmas (filmo_id),
            ziurovo_id INTEGER NOT NULL REFERENCES ziurovas (ziurovo_id),
            ivede_id INTEGER NOT NULL REFERENCES darbuotojas (darbuotojo_id),
            moderavo_id INTEGER REFERENCES darbuotojas (darbuotojo_id),
            UNIQUE (ziurovo_id, filmo_id)
        );
        CREATE TABLE ataskaita (
            ataskaitos_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pavadinimas TEXT NOT NULL,
            laikotarpis_nuo TEXT NOT NULL,
            laikotarpis_iki TEXT NOT NULL CHECK (laikotarpis_iki >= laikotarpis_nuo),
            sudarymo_data TEXT NOT NULL,
            darbuotojo_id INTEGER NOT NULL REFERENCES darbuotojas (darbuotojo_id)
        );
        CREATE TABLE ataskaitos_irasas (
            ataskaitos_id INTEGER NOT NULL REFERENCES ataskaita (ataskaitos_id) ON DELETE CASCADE,
            filmo_id INTEGER NOT NULL REFERENCES filmas (filmo_id),
            vieta INTEGER NOT NULL CHECK (vieta > 0),
            reitingas REAL NOT NULL CHECK (reitingas BETWEEN 1 AND 10),
            apzvalgu_skaicius INTEGER NOT NULL CHECK (apzvalgu_skaicius >= 0),
            PRIMARY KEY (ataskaitos_id, filmo_id)
        );
        """
    )
    pwd = slaptazodis("Apzvalga2026")
    zanrai = ["Drama", "Komedija", "Fantastika", "Trileris", "Veiksmas"]
    conn.executemany("INSERT INTO zanras (pavadinimas) VALUES (?)", [(z,) for z in zanrai])
    filmai = [
        ("Tarp pilkų debesų", "Marius Markevičius", 2018, 110, 1),
        ("Emilija iš Laisvės alėjos", "Donatas Ulvydas", 2017, 120, 1),
        ("Oppenheimer", "Christopher Nolan", 2023, 180, 1),
        ("Barbie", "Greta Gerwig", 2023, 114, 2),
        ("Dune: Antra dalis", "Denis Villeneuve", 2024, 166, 3),
        ("Konklava", "Edward Berger", 2024, 120, 4),
        ("Tadas Blinda. Pradžia", "Donatas Ulvydas", 2011, 110, 5),
    ]
    conn.executemany(
        """INSERT INTO filmas (pavadinimas, rezisierius, isleidimo_metai, trukme_min, zanro_id)
           VALUES (?, ?, ?, ?, ?)""",
        filmai,
    )
    ziurovai = [
        ("emilija.v", "Emilija", "Vaitkutė", "emilija.v@pastas.lt"),
        ("lukas.k", "Lukas", "Kazlauskas", "lukas.k@pastas.lt"),
        ("gabija.p", "Gabija", "Petraitytė", "gabija.p@pastas.lt"),
        ("tomas.b", "Tomas", "Balčiūnas", "tomas.b@pastas.lt"),
        ("austeja.s", "Austėja", "Stankevičiūtė", "austeja.s@pastas.lt"),
        ("nojus.m", "Nojus", "Mackevičius", "nojus.m@pastas.lt"),
    ]
    conn.executemany(
        """INSERT INTO ziurovas (naudotojo_vardas, vardas, pavarde, el_pastas)
           VALUES (?, ?, ?, ?)""",
        ziurovai,
    )
    darbuotojai = [
        ("Ieva", "Petrauskaitė", PAREIGOS[0], "specialistas", "ieva.petrauskaite@forumcinemas.lt", pwd),
        ("Mantas", "Kazlauskas", PAREIGOS[1], "moderatorius", "mantas.kazlauskas@forumcinemas.lt", pwd),
        ("Rūta", "Jankauskaitė", PAREIGOS[2], "vadybininkas", "ruta.jankauskaite@forumcinemas.lt", pwd),
    ]
    conn.executemany(
        """INSERT INTO darbuotojas
           (vardas, pavarde, pareigos, prisijungimo_vardas, el_pastas, slaptazodis)
           VALUES (?, ?, ?, ?, ?, ?)""",
        darbuotojai,
    )
    apzvalgos = [
        ("Labai jautrus ir stiprus filmas. Verta žiūrėti dideliame ekrane.", 9, "2026-10-03 14:10:00", "patvirtinta", None, "2026-10-03 16:00:00", 1, 1, 1, 2),
        ("Ilgas, bet nepalieka abejingų. Rekomenduoju.", 8, "2026-10-05 11:20:00", "patvirtinta", None, "2026-10-05 15:40:00", 1, 2, 1, 2),
        ("Graži vaidyba, tik pabaiga per daug ištęsta.", 7, "2026-10-08 18:05:00", "patvirtinta", None, "2026-10-08 19:10:00", 2, 3, 1, 2),
        ("Istorija įtraukia nuo pirmų minučių.", 9, "2026-10-12 12:00:00", "patvirtinta", None, "2026-10-12 13:15:00", 3, 1, 1, 2),
        ("Sunkus, bet labai gerai sudėliotas filmas.", 10, "2026-10-14 20:12:00", "patvirtinta", None, "2026-10-14 21:00:00", 3, 4, 1, 2),
        ("Linksmas ir netikėtas, tinka eiti su draugais.", 8, "2026-10-18 17:45:00", "patvirtinta", None, "2026-10-18 18:20:00", 4, 5, 1, 2),
        ("Vaizdas įspūdingas, istorija šiek tiek paini.", 7, "2026-10-21 19:30:00", "patvirtinta", None, "2026-10-21 20:05:00", 5, 2, 1, 2),
        ("Vienas gražiausių šių metų seansų.", 9, "2026-10-22 21:10:00", "patvirtinta", None, "2026-10-22 21:40:00", 5, 6, 1, 2),
        ("Įtampa laikosi visą filmą.", 8, "2026-10-25 16:18:00", "patvirtinta", None, "2026-10-25 17:00:00", 6, 3, 1, 2),
        ("Nuotykių užtenka, bet dialogai silpnoki.", 6, "2026-10-28 15:00:00", "patvirtinta", None, "2026-10-28 15:30:00", 7, 4, 1, 2),
        ("Norėčiau trumpesnio komentaro be siužeto atskleidimo.", 8, "2026-11-02 13:12:00", "atmesta", "Sutrumpinkite tekstą ir neaprašykite pabaigos.", None, 4, 6, 1, 2),
        ("Mačiau vakar. Labai patiko operatoriaus darbas.", 9, "2026-11-08 19:40:00", "laukia moderavimo", None, None, 2, 5, 1, None),
        ("Tinka tiems, kas mėgsta lėtą pasakojimą.", 7, "2026-11-09 11:05:00", "laukia moderavimo", None, None, 6, 1, 1, None),
    ]
    conn.executemany(
        """INSERT INTO apzvalga (
            tekstas, balas, pateikimo_data, busena, moderatoriaus_pastabos, publikavimo_data,
            filmo_id, ziurovo_id, ivede_id, moderavo_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        apzvalgos,
    )
    for filmo_id in range(1, 8):
        perskaiciuoti_reitinga(conn, filmo_id)
    conn.execute(
        """INSERT INTO ataskaita
           (pavadinimas, laikotarpis_nuo, laikotarpis_iki, sudarymo_data, darbuotojo_id)
           VALUES (?, ?, ?, ?, ?)""",
        ("Geriausiai įvertinti filmai", "2026-10-01", "2026-10-31", "2026-11-01", 3),
    )
    irasai = conn.execute(
        """
        SELECT f.filmo_id,
               ROUND(AVG(a.balas), 2) AS reitingas,
               COUNT(a.apzvalgos_id) AS kiekis
        FROM apzvalga a
        JOIN filmas f ON f.filmo_id = a.filmo_id
        WHERE a.busena = 'patvirtinta'
          AND date(a.publikavimo_data) BETWEEN '2026-10-01' AND '2026-10-31'
        GROUP BY f.filmo_id
        ORDER BY reitingas DESC, kiekis DESC, f.pavadinimas
        """
    ).fetchall()
    for vieta, row in enumerate(irasai, start=1):
        conn.execute(
            """INSERT INTO ataskaitos_irasas
               (ataskaitos_id, filmo_id, vieta, reitingas, apzvalgu_skaicius)
               VALUES (1, ?, ?, ?, ?)""",
            (row["filmo_id"], vieta, row["reitingas"], row["kiekis"]),
        )
    conn.commit()
    conn.close()


def vardas(row):
    return f"{row['vardas']} {row['pavarde']}"


def fmt_reitingas(reiksme):
    if reiksme is None:
        return "–"
    return f"{reiksme:.2f}".replace(".", ",")


def fmt_data(reiksme):
    if not reiksme:
        return "–"
    return reiksme[:16]


app.jinja_env.filters["reitingas"] = fmt_reitingas
app.jinja_env.filters["data"] = fmt_data


@app.context_processor
def bendras():
    return {"pareigos": session.get("pareigos"), "darbuotojas": session.get("darbuotojas")}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = db()
        user = conn.execute(
            "SELECT * FROM darbuotojas WHERE prisijungimo_vardas = ?",
            (request.form.get("vardas", "").strip(),),
        ).fetchone()
        conn.close()
        ivestas = slaptazodis(request.form.get("slaptazodis", ""))
        if user is None or user["slaptazodis"] != ivestas:
            flash("Neteisingas prisijungimo vardas arba slaptažodis.")
        else:
            session.clear()
            session["darbuotojo_id"] = user["darbuotojo_id"]
            session["pareigos"] = user["pareigos"]
            session["darbuotojas"] = vardas(user)
            return redirect(url_for("filmai"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def filmai():
    paieska = request.args.get("q", "").strip()
    conn = db()
    sql = """
        SELECT f.*, z.pavadinimas AS zanras,
               (SELECT COUNT(*) FROM apzvalga a
                WHERE a.filmo_id = f.filmo_id AND a.busena = 'patvirtinta') AS patvirtintos,
               (SELECT COUNT(*) FROM apzvalga a
                WHERE a.filmo_id = f.filmo_id AND a.busena = 'laukia moderavimo') AS laukia
        FROM filmas f
        JOIN zanras z ON z.zanro_id = f.zanro_id
    """
    params = []
    if paieska:
        sql += " WHERE f.pavadinimas LIKE ? OR f.rezisierius LIKE ? OR z.pavadinimas LIKE ?"
        like = f"%{paieska}%"
        params = [like, like, like]
    sql += " ORDER BY f.pavadinimas"
    eilutes = conn.execute(sql, params).fetchall()
    stats = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM filmas) AS filmu,
          (SELECT COUNT(*) FROM apzvalga WHERE busena = 'laukia moderavimo') AS laukia,
          (SELECT ROUND(AVG(reitingas), 2) FROM filmas WHERE reitingas IS NOT NULL) AS vidurkis
        """
    ).fetchone()
    conn.close()
    return render_template("filmai.html", filmai=eilutes, stats=stats, q=paieska)


@app.route("/filmas/<int:filmo_id>")
@login_required
def filmas(filmo_id):
    conn = db()
    filmas_row = conn.execute(
        """
        SELECT f.*, z.pavadinimas AS zanras
        FROM filmas f JOIN zanras z ON z.zanro_id = f.zanro_id
        WHERE f.filmo_id = ?
        """,
        (filmo_id,),
    ).fetchone()
    if filmas_row is None:
        conn.close()
        flash("Filmas nerastas.")
        return redirect(url_for("filmai"))
    apzvalgos = conn.execute(
        """
        SELECT a.*, z.vardas, z.pavarde
        FROM apzvalga a
        JOIN ziurovas z ON z.ziurovo_id = a.ziurovo_id
        WHERE a.filmo_id = ? AND a.busena = 'patvirtinta'
        ORDER BY a.publikavimo_data DESC
        """,
        (filmo_id,),
    ).fetchall()
    conn.close()
    return render_template("filmas.html", filmas=filmas_row, apzvalgos=apzvalgos)


@app.route("/apzvalgos")
@roles("Klientų aptarnavimo specialistas")
def apzvalgos():
    conn = db()
    eilutes = conn.execute(
        """
        SELECT a.*, f.pavadinimas AS filmas, z.vardas, z.pavarde, z.naudotojo_vardas
        FROM apzvalga a
        JOIN filmas f ON f.filmo_id = a.filmo_id
        JOIN ziurovas z ON z.ziurovo_id = a.ziurovo_id
        ORDER BY a.pateikimo_data DESC
        """
    ).fetchall()
    conn.close()
    return render_template("apzvalgos.html", apzvalgos=eilutes)


def _pasirinkimai():
    conn = db()
    filmai = conn.execute("SELECT filmo_id, pavadinimas FROM filmas ORDER BY pavadinimas").fetchall()
    ziurovai = conn.execute(
        "SELECT ziurovo_id, vardas, pavarde, naudotojo_vardas FROM ziurovas ORDER BY pavarde"
    ).fetchall()
    conn.close()
    return filmai, ziurovai


@app.route("/apzvalgos/nauja", methods=["GET", "POST"])
@roles("Klientų aptarnavimo specialistas")
def nauja_apzvalga():
    filmai, ziurovai = _pasirinkimai()
    if request.method == "POST":
        return _issaugoti_apzvalga(None, filmai, ziurovai)
    return render_template("apzvalga_forma.html", apzvalga=None, filmai=filmai, ziurovai=ziurovai)


@app.route("/apzvalgos/<int:apzvalgos_id>/redaguoti", methods=["GET", "POST"])
@roles("Klientų aptarnavimo specialistas")
def redaguoti_apzvalga(apzvalgos_id):
    conn = db()
    apzvalga = conn.execute("SELECT * FROM apzvalga WHERE apzvalgos_id = ?", (apzvalgos_id,)).fetchone()
    conn.close()
    if apzvalga is None:
        flash("Apžvalga nerasta.")
        return redirect(url_for("apzvalgos"))
    if apzvalga["busena"] == "patvirtinta":
        flash("Patvirtintos apžvalgos redaguoti negalima. Ji jau publikuota.")
        return redirect(url_for("apzvalgos"))
    filmai, ziurovai = _pasirinkimai()
    if request.method == "POST":
        return _issaugoti_apzvalga(apzvalgos_id, filmai, ziurovai)
    return render_template("apzvalga_forma.html", apzvalga=apzvalga, filmai=filmai, ziurovai=ziurovai)


def _issaugoti_apzvalga(apzvalgos_id, filmai, ziurovai):
    tekstas = request.form.get("tekstas", "").strip()
    try:
        balas = int(request.form.get("balas", ""))
        filmo_id = int(request.form.get("filmo_id", ""))
        ziurovo_id = int(request.form.get("ziurovo_id", ""))
    except ValueError:
        balas, filmo_id, ziurovo_id = 0, 0, 0
    if not tekstas or not (1 <= balas <= 10) or filmo_id <= 0 or ziurovo_id <= 0:
        flash("Užpildykite filmą, žiūrovą, balą nuo 1 iki 10 ir apžvalgos tekstą.")
        return render_template(
            "apzvalga_forma.html",
            apzvalga={"tekstas": tekstas, "balas": balas, "filmo_id": filmo_id, "ziurovo_id": ziurovo_id, "apzvalgos_id": apzvalgos_id},
            filmai=filmai,
            ziurovai=ziurovai,
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db()
    try:
        if apzvalgos_id is None:
            conn.execute(
                """INSERT INTO apzvalga (
                    tekstas, balas, pateikimo_data, busena, filmo_id, ziurovo_id, ivede_id
                ) VALUES (?, ?, ?, 'laukia moderavimo', ?, ?, ?)""",
                (tekstas, balas, now, filmo_id, ziurovo_id, session["darbuotojo_id"]),
            )
            flash("Apžvalga įvesta ir perduota moderuoti.")
        else:
            conn.execute(
                """UPDATE apzvalga
                   SET tekstas = ?, balas = ?, filmo_id = ?, ziurovo_id = ?,
                       busena = 'laukia moderavimo', moderatoriaus_pastabos = NULL,
                       publikavimo_data = NULL, moderavo_id = NULL, pateikimo_data = ?
                   WHERE apzvalgos_id = ?""",
                (tekstas, balas, filmo_id, ziurovo_id, now, apzvalgos_id),
            )
            flash("Apžvalga pataisyta ir vėl perduota moderuoti.")
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Šis žiūrovas šiam filmui apžvalgą jau yra pateikęs. Vienas žiūrovas filmą vertina tik vieną kartą.")
        conn.close()
        return render_template(
            "apzvalga_forma.html",
            apzvalga={"tekstas": tekstas, "balas": balas, "filmo_id": filmo_id, "ziurovo_id": ziurovo_id, "apzvalgos_id": apzvalgos_id},
            filmai=filmai,
            ziurovai=ziurovai,
        )
    conn.close()
    return redirect(url_for("apzvalgos"))


@app.route("/moderavimas")
@roles("Apžvalgų moderatorius")
def moderavimas():
    conn = db()
    eilutes = conn.execute(
        """
        SELECT a.*, f.pavadinimas AS filmas, z.vardas, z.pavarde
        FROM apzvalga a
        JOIN filmas f ON f.filmo_id = a.filmo_id
        JOIN ziurovas z ON z.ziurovo_id = a.ziurovo_id
        WHERE a.busena = 'laukia moderavimo'
        ORDER BY a.pateikimo_data
        """
    ).fetchall()
    conn.close()
    return render_template("moderavimas.html", apzvalgos=eilutes)


@app.route("/moderavimas/<int:apzvalgos_id>", methods=["POST"])
@roles("Apžvalgų moderatorius")
def moderuoti(apzvalgos_id):
    veiksmas = request.form.get("veiksmas")
    pastabos = request.form.get("pastabos", "").strip()
    conn = db()
    apzvalga = conn.execute("SELECT * FROM apzvalga WHERE apzvalgos_id = ?", (apzvalgos_id,)).fetchone()
    if apzvalga is None or apzvalga["busena"] != "laukia moderavimo":
        conn.close()
        flash("Ši apžvalga jau nebelaukia moderavimo.")
        return redirect(url_for("moderavimas"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if veiksmas == "patvirtinti":
        conn.execute(
            """UPDATE apzvalga
               SET busena = 'patvirtinta', publikavimo_data = ?, moderavo_id = ?, moderatoriaus_pastabos = NULL
               WHERE apzvalgos_id = ?""",
            (now, session["darbuotojo_id"], apzvalgos_id),
        )
        perskaiciuoti_reitinga(conn, apzvalga["filmo_id"])
        flash("Apžvalga publikuota. Filmo reitingas perskaičiuotas.")
    elif veiksmas == "atmesti":
        if not pastabos:
            conn.close()
            flash("Atmetant apžvalgą būtina įrašyti pastabas specialistui.")
            return redirect(url_for("moderavimas"))
        conn.execute(
            """UPDATE apzvalga
               SET busena = 'atmesta', moderatoriaus_pastabos = ?, moderavo_id = ?, publikavimo_data = NULL
               WHERE apzvalgos_id = ?""",
            (pastabos, session["darbuotojo_id"], apzvalgos_id),
        )
        flash("Apžvalga atmesta ir grąžinta taisyti.")
    conn.commit()
    conn.close()
    return redirect(url_for("moderavimas"))


@app.route("/ataskaitos", methods=["GET", "POST"])
@roles("Marketingo vadybininkas")
def ataskaitos():
    if request.method == "POST":
        pavadinimas = request.form.get("pavadinimas", "").strip()
        tipas = request.form.get("tipas", "")
        nuo = request.form.get("nuo", "")
        iki = request.form.get("iki", "")
        if not pavadinimas or tipas not in ("reitingas", "populiarumas") or not nuo or not iki or iki < nuo:
            flash("Nurodykite pavadinimą, ataskaitos rūšį ir teisingą laikotarpį.")
        else:
            conn = db()
            order = "reitingas DESC, kiekis DESC" if tipas == "reitingas" else "kiekis DESC, reitingas DESC"
            eilutes = conn.execute(
                f"""
                SELECT f.filmo_id,
                       ROUND(AVG(a.balas), 2) AS reitingas,
                       COUNT(a.apzvalgos_id) AS kiekis
                FROM apzvalga a
                JOIN filmas f ON f.filmo_id = a.filmo_id
                WHERE a.busena = 'patvirtinta'
                  AND date(a.publikavimo_data) BETWEEN ? AND ?
                GROUP BY f.filmo_id
                ORDER BY {order}, f.pavadinimas
                """,
                (nuo, iki),
            ).fetchall()
            if not eilutes:
                conn.close()
                flash("Pasirinktame laikotarpyje nėra patvirtintų apžvalgų.")
            else:
                siandien = datetime.now().strftime("%Y-%m-%d")
                cur = conn.execute(
                    """INSERT INTO ataskaita
                       (pavadinimas, laikotarpis_nuo, laikotarpis_iki, sudarymo_data, darbuotojo_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (pavadinimas, nuo, iki, siandien, session["darbuotojo_id"]),
                )
                ataskaitos_id = cur.lastrowid
                for vieta, row in enumerate(eilutes, start=1):
                    conn.execute(
                        """INSERT INTO ataskaitos_irasas
                           (ataskaitos_id, filmo_id, vieta, reitingas, apzvalgu_skaicius)
                           VALUES (?, ?, ?, ?, ?)""",
                        (ataskaitos_id, row["filmo_id"], vieta, row["reitingas"], row["kiekis"]),
                    )
                conn.commit()
                conn.close()
                flash("Ataskaita sudaryta. Joje įrašyti sudarymo metu buvę reitingai.")
                return redirect(url_for("ataskaita", ataskaitos_id=ataskaitos_id))
    conn = db()
    sarasas = conn.execute(
        """
        SELECT a.*, d.vardas, d.pavarde
        FROM ataskaita a
        JOIN darbuotojas d ON d.darbuotojo_id = a.darbuotojo_id
        ORDER BY a.sudarymo_data DESC, a.ataskaitos_id DESC
        """
    ).fetchall()
    conn.close()
    return render_template("ataskaitos.html", ataskaitos=sarasas)


@app.route("/ataskaitos/<int:ataskaitos_id>")
@roles("Marketingo vadybininkas")
def ataskaita(ataskaitos_id):
    conn = db()
    ataskaita_row = conn.execute(
        """
        SELECT a.*, d.vardas, d.pavarde
        FROM ataskaita a
        JOIN darbuotojas d ON d.darbuotojo_id = a.darbuotojo_id
        WHERE a.ataskaitos_id = ?
        """,
        (ataskaitos_id,),
    ).fetchone()
    if ataskaita_row is None:
        conn.close()
        flash("Ataskaita nerasta.")
        return redirect(url_for("ataskaitos"))
    irasai = conn.execute(
        """
        SELECT i.*, f.pavadinimas
        FROM ataskaitos_irasas i
        JOIN filmas f ON f.filmo_id = i.filmo_id
        WHERE i.ataskaitos_id = ?
        ORDER BY i.vieta
        """,
        (ataskaitos_id,),
    ).fetchall()
    conn.close()
    return render_template("ataskaita.html", ataskaita=ataskaita_row, irasai=irasai)


@app.route("/prieziura", methods=["GET", "POST"])
@roles("Marketingo vadybininkas")
def prieziura():
    conn = db()
    if request.method == "POST":
        veiksmas = request.form.get("veiksmas")
        try:
            if veiksmas == "zanras":
                pavadinimas = request.form.get("pavadinimas", "").strip()
                if not pavadinimas:
                    raise ValueError("Įrašykite žanro pavadinimą.")
                conn.execute("INSERT INTO zanras (pavadinimas) VALUES (?)", (pavadinimas,))
                flash("Žanras įrašytas.")
            elif veiksmas == "filmas":
                conn.execute(
                    """INSERT INTO filmas (pavadinimas, rezisierius, isleidimo_metai, trukme_min, zanro_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        request.form.get("pavadinimas", "").strip(),
                        request.form.get("rezisierius", "").strip(),
                        int(request.form.get("metai")),
                        int(request.form.get("trukme")),
                        int(request.form.get("zanro_id")),
                    ),
                )
                flash("Filmas įrašytas. Reitingas bus apskaičiuotas, kai atsiras patvirtintų apžvalgų.")
            elif veiksmas == "ziurovas":
                conn.execute(
                    """INSERT INTO ziurovas (naudotojo_vardas, vardas, pavarde, el_pastas)
                       VALUES (?, ?, ?, ?)""",
                    (
                        request.form.get("naudotojo_vardas", "").strip(),
                        request.form.get("vardas", "").strip(),
                        request.form.get("pavarde", "").strip(),
                        request.form.get("el_pastas", "").strip(),
                    ),
                )
                flash("Žiūrovas įrašytas.")
            elif veiksmas == "darbuotojas":
                pareigos = request.form.get("pareigos", "")
                if pareigos not in PAREIGOS:
                    raise ValueError("Pasirinkite pareigas iš sąrašo.")
                conn.execute(
                    """INSERT INTO darbuotojas
                       (vardas, pavarde, pareigos, prisijungimo_vardas, el_pastas, slaptazodis)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        request.form.get("vardas", "").strip(),
                        request.form.get("pavarde", "").strip(),
                        pareigos,
                        request.form.get("prisijungimo_vardas", "").strip(),
                        request.form.get("el_pastas", "").strip(),
                        slaptazodis(request.form.get("slaptazodis", "")),
                    ),
                )
                flash("Darbuotojo paskyra sukurta.")
            conn.commit()
        except (sqlite3.IntegrityError, ValueError) as exc:
            flash("Duomenų įrašyti nepavyko. Patikrinkite, ar pavadinimas arba el. paštas nepasikartoja, ir ar laukai užpildyti.")
            if str(exc):
                pass
    zanrai = conn.execute("SELECT * FROM zanras ORDER BY pavadinimas").fetchall()
    filmai = conn.execute(
        """SELECT f.pavadinimas, f.isleidimo_metai, z.pavadinimas AS zanras
           FROM filmas f JOIN zanras z ON z.zanro_id = f.zanro_id
           ORDER BY f.pavadinimas"""
    ).fetchall()
    ziurovai = conn.execute("SELECT * FROM ziurovas ORDER BY pavarde").fetchall()
    darbuotojai = conn.execute(
        "SELECT vardas, pavarde, pareigos, prisijungimo_vardas, el_pastas FROM darbuotojas ORDER BY pareigos, pavarde"
    ).fetchall()
    conn.close()
    return render_template(
        "prieziura.html",
        zanrai=zanrai,
        filmai=filmai,
        ziurovai=ziurovai,
        darbuotojai=darbuotojai,
        pareigu_sarasas=PAREIGOS,
    )


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5055")),
        debug=False,
    )
