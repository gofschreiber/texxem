# Spezifikation: Betriebskostenabrechnung für ein kleines Mehrfamilienhaus

## Phase 1 – Datenbankstruktur

## 1. Geltungsbereich & bestätigte Eckdaten

| Thema | Entscheidung |
|---|---|
| Mandantenfähigkeit | Single-Mandant (ein Eigentümer/Betreiber) |
| Verteilerschlüssel | Fester Katalog: Wohnfläche, Personenzahl, Anzahl Einheiten, Miteigentumsanteile, Verbrauch |
| Zeitanteilige Abrechnung bei Ein-/Auszug | Ja, taggenau automatisch |
| Leerstand | Automatisch aus Lücken zwischen Mietverhältnissen abgeleitet (keine eigene Erfassung); Kosten gehen zulasten des Eigentümers |
| Vorauszahlungen | Kein laufendes Ledger – werden einmalig je Abrechnungsjahr bei Erstellung der Abrechnung als Jahresbetrag erfasst |
| Kostenarten-Katalog | Fest nach § 2 BetrKV (17 Positionen), nicht erweiterbar |
| Gewerbeeinheiten | Möglich (eine Gewerbeeinheit), ohne umsatzsteuerliche Sonderbehandlung; Eigentümer ist eine nicht vorsteuerabzugsberechtigte KG |
| Belege | Optionaler Datei-Upload je Kostenposition |
| Abrechnungsperiode | Immer Kalenderjahr; unterjährige Ein-/Auszüge werden taggenau abgegrenzt; ausgezogene Mieter erhalten ihre Abrechnung im Folgejahr zusammen mit allen anderen |
| Zuordnung der Kosten zum Jahr | Je Kostenposition wählbar: Abflussprinzip **oder** periodengerechte Abgrenzung (tagesgenau oder über manuellen Stichtags-Zählerstand) |
| Verbrauchsdaten | Schnittstelle liefert **tagesgenaue, absolute Zählerstände**; Verteilung/Berechnung erfolgt in dieser Applikation |
| Heizkosten/Warmwasser | Mischkalkulation nach HeizkostenV: Grundkosten (i. d. R. nach Fläche) + Verbrauchskosten (nach Zähler), Split-Prozentsatz konfigurierbar |
| Zählertypen | Erweiterbarer Katalog, mind. Heizung, Warmwasser, Kaltwasser, Allgemeinstrom |
| Mieter je Mietverhältnis | Genau ein Mieter-Datensatz pro Mietverhältnis (Haushaltsvorstand) |
| Personenzahl | Einfacher aktueller Wert je Mietverhältnis, keine Historisierung. Es werden keine Kostenarten nach Personen verteilt; verbrauchsabhängige Kosten werden direkt über Erfassungsgeräte den Wohnungen zugeordnet |
| Nachsendeadresse | Wird erfasst, da ausgezogene Mieter ihre Abrechnung erst im Folgejahr erhalten |
| Zugang | Nur Betreiber (`benutzer`); Mieter haben keinen eigenen Zugang |

Nicht explizit erfragte Punkte sind in Abschnitt 7 als **Annahmen** gekennzeichnet.

## 2. Entitäten-Übersicht

```
Eigentuemer ──< Objekt ──< Wohneinheit ──< Mietverhaeltnis >── Mieter
                   │              │
                   │              └──< Zaehler ──< Zaehlerstand
                   │
                   ├──< Kosten ──< KostenBeleg
                   │       └──< KostenJahresanteil
                   │
                   ├──< ObjektKostenartKonfiguration >── Kostenart
                   │                                 └── Verteilerschluessel
                   │                                 └── Zaehlertyp
                   │
                   └──< Abrechnung ──< AbrechnungPosition >── Mietverhaeltnis
                                              └──< AbrechnungPositionKostenart >── Kostenart
```

## 3. Tabellen im Detail

### 3.1 `eigentuemer`
Rechts-/Steuersubjekt, dem ein oder mehrere Objekte gehören (Briefkopf, Bankverbindung für Erstattungen).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| name | VARCHAR | Firmen- oder Personenname |
| rechtsform | VARCHAR | z. B. "KG", "natürliche Person" |
| strasse, plz, ort | VARCHAR | |
| vorsteuerabzugsberechtigt | BOOLEAN | nur informativ, keine USt-Logik |
| iban, bic | VARCHAR, NULLABLE | |
| erstellt_am, geaendert_am | TIMESTAMP | |

### 3.2 `objekt`
Ein Gebäude/eine Liegenschaft.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| eigentuemer_id | FK → eigentuemer | |
| bezeichnung | VARCHAR | z. B. "Hauptstraße 12" |
| strasse, hausnummer, plz, ort | VARCHAR | |
| baujahr | INTEGER, NULLABLE | |
| erstellt_am, geaendert_am | TIMESTAMP | |

### 3.3 `wohneinheit`
Wohnung oder Gewerbeeinheit innerhalb eines Objekts.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| objekt_id | FK → objekt | |
| bezeichnung | VARCHAR | z. B. "EG links" |
| typ | ENUM('WOHNUNG','GEWERBE') | |
| wohnflaeche_m2 | NUMERIC(8,2) | Basis für Verteilerschlüssel Fläche |
| miteigentumsanteile | NUMERIC(10,4), NULLABLE | nur falls MEA-Schlüssel genutzt wird |
| verfuegbar_ab | DATE | Datum, ab dem die Einheit vermietbar ist (Startpunkt für Leerstandsberechnung) |
| erstellt_am, geaendert_am | TIMESTAMP | |

Constraint: `UNIQUE(objekt_id, bezeichnung)`

### 3.4 `mieter`
Stammdaten, kein eigener Applikationszugang.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| anrede | VARCHAR, NULLABLE | |
| vorname, nachname | VARCHAR | bzw. Firmenname bei Gewerbe |
| telefon, email | VARCHAR, NULLABLE | |
| iban, bic | VARCHAR, NULLABLE | für Guthabenauszahlung |
| nachsendeadresse_strasse, _plz, _ort | VARCHAR, NULLABLE | wird nach Auszug gepflegt |
| nachsendeadresse_gueltig_ab | DATE, NULLABLE | |
| notizen | TEXT, NULLABLE | |
| erstellt_am, geaendert_am | TIMESTAMP | |

### 3.5 `mietverhaeltnis`
Verknüpft einen Mieter mit einer Wohneinheit über einen Zeitraum. Ein Mieter kann über die Zeit mehrere Mietverhältnisse haben (Umzug innerhalb des Hauses, erneuter Einzug).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| wohneinheit_id | FK → wohneinheit | |
| mieter_id | FK → mieter | |
| einzugsdatum | DATE, NOT NULL | |
| auszugsdatum | DATE, NULLABLE | NULL = laufendes Mietverhältnis |
| personenanzahl | INTEGER, NOT NULL, DEFAULT 1 | aktueller Wert, keine Historisierung |
| erstellt_am, geaendert_am | TIMESTAMP | |

Regeln (Business-Logik, nicht als eigene Tabelle):
- `CHECK (auszugsdatum IS NULL OR auszugsdatum >= einzugsdatum)`
- Anwendungsseitig sicherstellen, dass sich Zeiträume zweier Mietverhältnisse derselben Wohneinheit nicht überlappen.
- **Leerstand** = jeder Tag zwischen `wohneinheit.verfuegbar_ab` (bzw. Ende des letzten Mietverhältnisses) und dem nächsten `einzugsdatum`, an dem kein Mietverhältnis aktiv ist. Wird zur Laufzeit berechnet, nicht gespeichert.

### 3.6 `kostenart` (Stammdaten, fix nach § 2 BetrKV)

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| nummer_betrkv | VARCHAR | z. B. "2 Nr. 4" |
| bezeichnung | VARCHAR | |
| verbrauchsabhaengig_moeglich | BOOLEAN | Kennzeichen, ob Kostenart an einen Zähler gekoppelt werden kann |

Seed-Daten (17 Positionen):

| Nr. | Bezeichnung | verbrauchsabhängig möglich |
|---|---|---|
| 1 | Grundsteuer | nein |
| 2 | Kosten der Wasserversorgung | ja (Kaltwasser) |
| 3 | Kosten der Entwässerung | nein |
| 4 | Kosten der Heizungsanlage | ja (Heizung, mit Grundkosten-Split) |
| 5 | Kosten der Warmwasserversorgung | ja (Warmwasser, mit Grundkosten-Split) |
| 6 | Kosten verbundener Heizungs-/Warmwasseranlagen | ja (Heizung, mit Grundkosten-Split) |
| 7 | Kosten des Aufzugs | nein |
| 8 | Straßenreinigung und Müllbeseitigung | nein |
| 9 | Gebäudereinigung und Ungezieferbekämpfung | nein |
| 10 | Gartenpflege | nein |
| 11 | Beleuchtung | ja (Allgemeinstrom, optional) |
| 12 | Schornsteinreinigung | nein |
| 13 | Sach- und Haftpflichtversicherung | nein |
| 14 | Hauswart | nein |
| 15 | Gemeinschafts-Antenne/Kabelanschluss | nein |
| 16 | Einrichtungen der Wäschepflege | nein |
| 17 | Sonstige Betriebskosten | nein |

### 3.7 `verteilerschluessel` (Stammdaten, fix)

| id | code | bezeichnung |
|---|---|---|
| 1 | WOHNFLAECHE | nach m² |
| 2 | PERSONENANZAHL | nach Personenzahl |
| 3 | ANZAHL_EINHEITEN | nach Anzahl Wohneinheiten |
| 4 | MITEIGENTUMSANTEILE | nach MEA |
| 5 | VERBRAUCH | nach gemessenem Verbrauch |

### 3.8 `zaehlertyp` (erweiterbarer Katalog)

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| bezeichnung | VARCHAR | z. B. "Heizung", "Warmwasser", "Kaltwasser", "Allgemeinstrom" |
| einheit | VARCHAR | z. B. "kWh", "m³" |
| aktiv | BOOLEAN | |

### 3.9 `objekt_kostenart_konfiguration`
Pro Objekt wird festgelegt, mit welchem Schlüssel eine Kostenart verteilt wird. Historisierbar, falls sich die Zuordnung ändert (z. B. nachträglicher Einbau von Zählern).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| objekt_id | FK → objekt | |
| kostenart_id | FK → kostenart | |
| verteilerschluessel_id | FK → verteilerschluessel | |
| ist_verbrauchsabhaengig | BOOLEAN | ob Zählerdaten einbezogen werden |
| grundkosten_anteil_prozent | NUMERIC(5,2), NULLABLE | z. B. 30.00 = 30 % nach Fläche, Rest nach Verbrauch; nur bei Heizung/Warmwasser |
| zaehlertyp_id | FK → zaehlertyp, NULLABLE | welcher Zählertyp liefert die Verbrauchswerte |
| gueltig_ab | DATE | |
| gueltig_bis | DATE, NULLABLE | |

Constraint: `UNIQUE(objekt_id, kostenart_id, gueltig_ab)`

### 3.10 `zaehler`
Physisches Erfassungsgerät, zugeordnet zu einer Wohneinheit oder – bei Allgemeinstrom – zum Objekt.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| zaehlertyp_id | FK → zaehlertyp | |
| wohneinheit_id | FK → wohneinheit, NULLABLE | |
| objekt_id | FK → objekt, NULLABLE | für objektweite Zähler (z. B. Allgemeinstrom) |
| externe_geraete_id | VARCHAR | ID/Seriennummer aus der externen Messapplikation, für Schnittstellen-Abgleich |
| einbaudatum | DATE | |
| ausbaudatum | DATE, NULLABLE | bei Gerätewechsel |
| erstellt_am | TIMESTAMP | |

Constraint: `CHECK (wohneinheit_id IS NOT NULL OR objekt_id IS NOT NULL)`

### 3.11 `zaehlerstand`
Tagesgenaue Ablesewerte, importiert via Schnittstelle oder manuell (z. B. für Stichtagsabgrenzung bei Fremdabrechnungen wie Strom).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| zaehler_id | FK → zaehler | |
| ablesedatum | DATE | |
| stand | NUMERIC(14,4) | absoluter Zählerstand |
| quelle | ENUM('SCHNITTSTELLE','MANUELL') | |
| importiert_am | TIMESTAMP, NULLABLE | |

Constraint: `UNIQUE(zaehler_id, ablesedatum)`

### 3.12 `kosten`
Einzelne erfasste Kostenposition (Rechnung/Ausgabe).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| objekt_id | FK → objekt | |
| kostenart_id | FK → kostenart | |
| betrag_gesamt | NUMERIC(10,2) | |
| rechnungsdatum | DATE | |
| leistungszeitraum_von | DATE | |
| leistungszeitraum_bis | DATE | |
| abgrenzungsart | ENUM('ABFLUSSPRINZIP','PERIODENGERECHT_TAGESGENAU','PERIODENGERECHT_ZAEHLERSTAND') | |
| lieferant | VARCHAR, NULLABLE | |
| beschreibung | TEXT, NULLABLE | |
| erstellt_am, geaendert_am | TIMESTAMP | |

Constraint: `CHECK (leistungszeitraum_bis >= leistungszeitraum_von)`

### 3.13 `kosten_jahresanteil`
Abgrenzungsergebnis: welcher Anteil einer Kostenposition welchem Abrechnungsjahr zugeordnet wird. Bei `ABFLUSSPRINZIP` entsteht genau eine Zeile (100 % im Jahr des `rechnungsdatum`); bei periodengerechter Abgrenzung ggf. mehrere Zeilen über Jahresgrenzen hinweg.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| kosten_id | FK → kosten | |
| abrechnungsjahr | INTEGER | |
| betrag_anteil | NUMERIC(10,2) | |
| berechnungsgrundlage | TEXT | z. B. "184 von 365 Tagen" oder "Zählerstand 31.12. lt. manueller Ablesung" |
| referenz_zaehlerstand_id | FK → zaehlerstand, NULLABLE | bei `PERIODENGERECHT_ZAEHLERSTAND` |

### 3.14 `kosten_beleg`
Dateianhänge zu einer Kostenposition.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| kosten_id | FK → kosten | |
| dateiname | VARCHAR | |
| speicherreferenz | VARCHAR | Pfad/Objekt-Key im Dateispeicher |
| mime_type | VARCHAR | |
| hochgeladen_am | TIMESTAMP | |

### 3.15 `abrechnung`
Ein Abrechnungslauf für ein Objekt und ein Kalenderjahr.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| objekt_id | FK → objekt | |
| abrechnungsjahr | INTEGER | |
| status | ENUM('ENTWURF','FINALISIERT','VERSENDET') | |
| erstellt_am | TIMESTAMP | |

Constraint: `UNIQUE(objekt_id, abrechnungsjahr)`

### 3.16 `abrechnungsposition`
Eine Zeile je Mietverhältnis, das im Abrechnungsjahr (auch nur anteilig) aktiv war – inkl. bereits ausgezogener Mieter.

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| abrechnung_id | FK → abrechnung | |
| mietverhaeltnis_id | FK → mietverhaeltnis | |
| zeitraum_von, zeitraum_bis | DATE | Schnittmenge aus Mietverhältnis-Zeitraum und Kalenderjahr |
| nutzungstage | INTEGER | |
| vorauszahlung_erhalten | NUMERIC(10,2), DEFAULT 0 | einmalig bei Abrechnungserstellung erfasst |
| kostenanteil_gesamt | NUMERIC(10,2) | Summe der zugeordneten Kosten |
| saldo | NUMERIC(10,2) | kostenanteil_gesamt − vorauszahlung_erhalten (positiv = Nachzahlung, negativ = Guthaben) |
| zustelladresse_strasse, _plz, _ort | VARCHAR | Snapshot zum Zeitpunkt der Erstellung (aktuelle Adresse oder Nachsendeadresse) |
| erstellt_am | TIMESTAMP | |

### 3.17 `abrechnungsposition_kostenart`
Detailzeilen je Kostenart innerhalb einer Abrechnungsposition (für den Ausweis auf dem Abrechnungsdokument).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| abrechnungsposition_id | FK → abrechnungsposition | |
| kostenart_id | FK → kostenart | |
| verteilerschluessel_id | FK → verteilerschluessel | |
| betrag | NUMERIC(10,2) | |
| grundkosten_betrag | NUMERIC(10,2), NULLABLE | nur bei Heizung/Warmwasser mit Split |
| verbrauchskosten_betrag | NUMERIC(10,2), NULLABLE | nur bei Heizung/Warmwasser mit Split |
| verbrauchswert | NUMERIC(14,4), NULLABLE | z. B. m³/kWh, zur Transparenz |
| anteil_prozent | NUMERIC(7,4), NULLABLE | Anteil an Gesamtbasis |

### 3.18 `benutzer`
Einfacher Admin-Zugang für den Betreiber (Mieter haben keinen Zugang).

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | PK | |
| benutzername, email | VARCHAR | |
| passwort_hash | VARCHAR | |
| aktiv | BOOLEAN | |
| erstellt_am, letzter_login | TIMESTAMP | |

## 4. Fachliche Kernregeln

1. **Nutzungstage je Mietverhältnis**: Schnittmenge aus Mietverhältnis-Zeitraum und Kalenderjahr (inkl. Einzugs- und Auszugstag).
2. **Leerstand**: Tage ohne aktives Mietverhältnis werden dem Eigentümer zugerechnet und fließen als "Eigentümer-Anteil" in die Gesamtbasis (Nutzungstage × Basiswert) ein.
3. **Flächen-/Personen-/Einheiten-/MEA-basierte Kostenarten**: Umlage = Gesamtkosten × (Basiswert der Einheit × Nutzungstage) / Σ(Basiswert aller Einheiten × deren Nutzungstage im Jahr).
4. **Verbrauchsabhängige Kostenarten ohne Split** (z. B. Kaltwasser): Verbrauch je Mietverhältnis = Differenz der Zählerstände am Ein-/Auszugsdatum (bzw. Jahresanfang/-ende).
5. **Heizung/Warmwasser mit Grundkosten-Split**: Gesamtkosten werden gemäß `grundkosten_anteil_prozent` aufgeteilt; Grundkostenanteil nach Fläche/Nutzungstagen (wie Punkt 3), Verbrauchskostenanteil nach Zählerdifferenz (wie Punkt 4).
6. **Jahresabgrenzung von Kosten**: Bei `ABFLUSSPRINZIP` 100 % im Jahr des Rechnungsdatums. Bei `PERIODENGERECHT_TAGESGENAU` tageweise Aufteilung des Leistungszeitraums auf die betroffenen Kalenderjahre. Bei `PERIODENGERECHT_ZAEHLERSTAND` Aufteilung anhand eines manuell erfassten Stichtags-Zählerstands (z. B. 31.12.).
7. **Ausgezogene Mieter**: bleiben über `mietverhaeltnis` referenzierbar und erhalten über `abrechnungsposition` ihre Abrechnung im Folgejahr, zugestellt an die Nachsendeadresse (falls gepflegt).

## 5. Schnittstelle Verbrauchsdaten (konzeptionell)

- Die externe Mess-Applikation liefert pro Zähler (`externe_geraete_id`) tagesgenaue, absolute Zählerstände.
- Vorschlag: REST-Endpoint, z. B. `POST /api/v1/zaehlerstaende` mit Payload-Array `{ externe_geraete_id, ablesedatum, stand }`.
- Zuordnung zum internen `zaehler`-Datensatz über `externe_geraete_id`.
- Upsert-Logik über `UNIQUE(zaehler_id, ablesedatum)` – erneute Lieferung desselben Tages überschreibt den Wert.
- Authentifizierung (z. B. API-Key) und genaues Zielformat werden in einer eigenen Folgephase (API-Spezifikation) definiert.

## 6. Offen für Folgephasen

- API-/Business-Logik-Spezifikation (Berechnungs-Engine im Detail, Rundungsregeln)
- UI/Screens (Erfassung Objekte, Wohneinheiten, Mieter, Kosten, Abrechnungslauf) → spezifiziert in Phase 2, Abschnitte 10–19
- Druckvorlage/PDF-Layout der Abrechnung
- Feingranulare Rechteverwaltung für `benutzer` im Detail (derzeit nur eine Rolle vorgesehen; Auth-Technologie siehe Abschnitt 8.1)
- Konkretes Schnittstellenformat/-protokoll mit der externen Messapplikation

## 7. Getroffene Annahmen (zur Bestätigung)

- Währung ausschließlich EUR (keine Mehrwährungsfähigkeit).
- Jede Kostenposition betrifft genau ein Objekt (keine geteilten Kosten über mehrere Objekte/Wirtschaftseinheiten hinweg).
- Keine Überschneidung zweier Mietverhältnisse derselben Wohneinheit (wird anwendungsseitig verhindert).

## 8. Technischer Stack & Implementierungsrichtlinien

Diese Spezifikation bleibt dauerhaft auf Deutsch, inklusive aller zukünftigen Ergänzungen. Entwicklungs-/Tooling-Konventionen
für Code und Repository (Sprache des Codes, Projektstruktur, Build-/Testbefehle) sind in `.github/copilot-instructions.md`
dokumentiert und werden hier nicht dupliziert; dieser Abschnitt hält die fachlich relevanten technischen Rahmenentscheidungen
fest, die direkt Auswirkungen auf das Datenmodell bzw. den Betrieb der Anwendung haben.

### 8.1 Technologie-Stack

| Bereich | Entscheidung |
|---|---|
| Backend-Sprache/-Framework | Python 3.12, Flask |
| Datenbank | MariaDB |
| Datenbankzugriff | SQLAlchemy (Flask-SQLAlchemy) als ORM; Tabellen-/Spaltennamen bleiben wie in Abschnitt 3 definiert (deutsch) |
| Schemamigrationen | Alembic (Flask-Migrate) |
| Authentifizierung (`benutzer`) | Flask-Login; Passwort-Hashing über Werkzeug (`generate_password_hash`/`check_password_hash`) |
| CSRF-Schutz (UI, Phase 2) | Flask-WTF (`CSRFProtect`), siehe Abschnitt 16 und Annahme A3 |
| Dependency-Management | pip + venv, `requirements.txt` |
| Tests | pytest |
| Code-Stil/Linting | ruff |
| Anwendungssprache (UI) | Deutsch, unter Verwendung der etablierten mietrechtlichen Fachbegriffe |
| Quellcode (Bezeichner) | Englisch; Datenbankschema bleibt deutsch (siehe `.github/copilot-instructions.md`) |

### 8.2 Konfiguration

- Alle Konfigurationswerte (DB-Zugangsdaten, Flask-Secret-Key, Logging-Einstellungen, Upload-Verzeichnis usw.) liegen zentral
  in einer einzigen Datei `config.json` im Projekt-Root, im JSON-Format.
- `config.json` wird bewusst mit ins Git-Repository eingecheckt (keine Trennung in `.gitignore` + Beispieldatei).

### 8.3 Logging

- Alle Module schreiben in dieselbe Logdatei (gemeinsamer Logger-Baum, an den Root-Logger propagierend).
- Bei jedem Anwendungsstart wird eine neue Logdatei mit Start-Zeitstempel im Dateinamen angelegt
  (z. B. `log/app_20260101_153000.log`) – das entspricht einem neuen „Block“ pro Programmstart.
- Die Logdateien liegen im Unterverzeichnis `log/` des Projekts.
- Es werden maximal die 5 letzten Logdateien aufgehoben; ältere werden beim Start automatisch gelöscht.

### 8.4 Reverse Proxy / Transportverschlüsselung

- Die Anwendung läuft hinter einem Reverse Proxy, der TLS/HTTPS terminiert; die Flask-Anwendung selbst liefert nur HTTP aus.
- Der Reverse Proxy liefert bereits korrekte Weiterleitungs-Header; die Anwendung benötigt dafür keine zusätzliche Middleware.
- Session-Cookies werden unabhängig davon zusätzlich mit `Secure`, `HttpOnly` und `SameSite=Lax` abgesichert.

### 8.5 Datei-Uploads (Belege)

- Belege (`kosten_beleg.speicherreferenz`) werden im lokalen Dateisystem gespeichert; das Basisverzeichnis ist in
  `config.json` konfigurierbar (Default: `./uploads`).
- Kein hartes Limit für Dateigröße oder MIME-Type in der ersten Ausbaustufe.

### 8.6 Betrieb als Dienst

- Die Anwendung läuft als systemd-Dienst `texxem.service` (Vorlage: `deploy/texxem.service`) unter dem Benutzer `gerald`,
  ausgeliefert über gunicorn (`--preload`, 2 Worker) auf `0.0.0.0:8000` (im lokalen Netz erreichbar, z. B. `http://192.168.0.27:8000`); ein Reverse Proxy kann dorthin weiterleiten.
- Der Dienst startet beim Systemstart nach MariaDB automatisch und wird bei Fehlern (`Restart=on-failure`) nach 5 Sekunden
  neu gestartet. Nach 5 fehlgeschlagenen Starts innerhalb von 5 Minuten bleibt er im Zustand „failed“, statt endlos
  weiter neu zu starten.
- Ausgaben von gunicorn landen im systemd-Journal (`journalctl -u texxem`); die Anwendungslogs liegen wie in 8.3 in `log/`.
## 9. Umsetzung Phase 1 – Konkretisierungen des Datenbankschemas

Die Tabellen aus Abschnitt 3 sind per Alembic-Migration (`migrations/versions/0001_initial_schema.py`) umgesetzt, inklusive
Seed-Daten für `kostenart` (17 Positionen, `id` = laufende Nummer, `nummer_betrkv` = „2 Nr. *n*“), `verteilerschluessel`
(5 Schlüssel mit den `id`-Werten aus 3.7) und `zaehlertyp` (Heizung/kWh, Warmwasser/m³, Kaltwasser/m³, Allgemeinstrom/kWh,
alle aktiv). Darüber hinaus gelten folgende technische Festlegungen:

| Thema | Festlegung |
|---|---|
| Datenbank/Zeichensatz | Datenbank `texxem`, `utf8mb4` / `utf8mb4_unicode_ci`; Treiber PyMySQL |
| Primärschlüssel | `INTEGER`, Auto-Increment |
| Spalten ohne „NULLABLE“-Vermerk | `NOT NULL` |
| Zeitstempel | `erstellt_am` = `CURRENT_TIMESTAMP`; `geaendert_am` zusätzlich `ON UPDATE CURRENT_TIMESTAMP` |
| Fremdschlüssel | `ON DELETE RESTRICT` (Standard); kein kaskadierendes Löschen |
| Standardwerte | `vorsteuerabzugsberechtigt` = false, `aktiv` = true, `personenanzahl` = 1, `abrechnung.status` = `ENTWURF`, `vorauszahlung_erhalten` = 0 |
| Zusätzliche Eindeutigkeit | `kostenart.nummer_betrkv`, `verteilerschluessel.code`, `zaehler.externe_geraete_id` (Schnittstellen-Zuordnung, Abschnitt 5), `benutzer.benutzername`, `benutzer.email`, `abrechnungsposition(abrechnung_id, mietverhaeltnis_id)` (eine Zeile je Mietverhältnis) |
| CHECK-Constraints | wie in 3.5, 3.10 und 3.12 spezifiziert (in MariaDB als echte `CHECK`-Constraints) |

Spaltenlängen (`VARCHAR`):

| Länge | Spalten |
|---|---|
| 255 | `name`, `bezeichnung`, `email`, `lieferant`, `dateiname`, `passwort_hash` |
| 500 | `kosten_beleg.speicherreferenz` |
| 150 | `strasse`, `nachsendeadresse_strasse`, `zustelladresse_strasse`, `vorname`, `nachname` |
| 100 | `ort` (und `nachsendeadresse_ort`, `zustelladresse_ort`), `rechtsform`, `externe_geraete_id`, `benutzername`, `zaehlertyp.bezeichnung` |
| 50 | `anrede`, `telefon`, `verteilerschluessel.code` |
| 34 / 11 | `iban` / `bic` |
| 20 | `hausnummer`, `zaehlertyp.einheit`, `nummer_betrkv` |
| 10 | `plz` (und `nachsendeadresse_plz`, `zustelladresse_plz`) |
| 127 | `mime_type` |

Nicht Bestandteil von Phase 1 (siehe Abschnitt 6): REST-Schnittstelle für Zählerstände, Berechnungs-Engine
(Nutzungstage, Leerstand, Abgrenzung, Umlage), anwendungsseitige Überschneidungsprüfung von Mietverhältnissen, UI (siehe
Phase 2) und Druckvorlage.

---

## Phase 2 – Web-UI

## 10. Grundprinzipien

| Thema | Entscheidung |
|---|---|
| Architektur | Serverseitig gerendert (Flask + Jinja2), kein Single-Page-Framework. Jede Seite funktioniert ohne JavaScript; JavaScript (Vanilla, ohne Bibliotheken) ist nur optionale Verbesserung |
| Sprache | Deutsch, mit den Fachbegriffen aus Abschnitt 1–4 (Mietverhältnis, Wohneinheit, Betriebskostenabrechnung …) |
| Zugang | Ausschließlich angemeldete `benutzer`; alle Seiten außer Login sind geschützt (Abschnitt 14.1) |
| Externe Ressourcen | Keine CDNs, keine externen Schriften/Icons; alle Assets liegen unter `app/static/` |
| Design | Genau **eine** zentrale CSS-Datei (Abschnitt 17); Templates enthalten weder `style`-Attribute noch `<style>`-Blöcke |
| Konsistenz | Alle Entitäten verwenden dasselbe Muster für Anlegen, Bearbeiten und Löschen (Abschnitt 12) und dieselbe Darstellung für Hierarchien (Abschnitt 13) |
| Sicherheit | CSRF-Token in jedem schreibenden Formular; Löschen und Ändern nur per `POST`; Session-Cookie-Härtung wie in 8.4 |
| Darstellung von Werten | Datum `TT.MM.JJJJ`, Beträge `1.234,56 €`, Dezimalzahlen mit Komma, Flächen `65,50 m²`; Eingabe von Datumswerten über `<input type="date">`, von Zahlen mit Komma oder Punkt |

## 11. Seitenaufbau & Navigation

### 11.1 Layout (für alle Seiten identisch)

```
┌──────────────────────────────────────────────────────────────┐
│ Kopfzeile: Anwendungsname │ aktives Objekt ▾ │ Benutzer ▾     │
├────────────┬─────────────────────────────────────────────────┤
│ Navigation │ Brotkrumen (Breadcrumb)                         │
│ (links)    │ Seitentitel                    [Primäre Aktion] │
│            │ Meldungen (Flash)                               │
│            │ Inhalt: Liste | Baum | Formular | Detail        │
└────────────┴─────────────────────────────────────────────────┘
```

- **Kopfzeile**: Anwendungsname, Auswahl des **aktiven Objekts** (Abschnitt 11.3), Benutzermenü (Passwort ändern, Abmelden).
  Im Testmodus (Abschnitt 18) zusätzlich ein deutlich sichtbares Banner „TESTMODUS – Testdatenbank“.
- **Navigation** (links, feste Reihenfolge, aktiver Punkt hervorgehoben):

  | Gruppe | Menüpunkte |
  |---|---|
  | – | Übersicht |
  | Stammdaten | Eigentümer · Objekte & Wohneinheiten · Mieter |
  | Messwesen | Zähler & Zählerstände · Zählertypen |
  | Kosten | Kostenpositionen · Verteilung (Konfiguration je Kostenart) · Kostenarten (nur Ansicht) |
  | Abrechnung | Abrechnungen |
  | System | Benutzer |

- **Brotkrumen** zeigen immer den vollständigen Pfad (z. B. *Objekte › Hauptstraße 12 › EG links › Mietverhältnis 01.03.2024*).
- **Seitentitel und primäre Aktion** stehen immer in derselben Zeile; die primäre Aktion (z. B. „Neu anlegen“) steht
  immer rechts oben.
- **Meldungen** (Flash) erscheinen immer unter dem Seitentitel; Typen: Erfolg, Hinweis, Fehler.

### 11.2 Seitentypen

Jede Seite gehört zu genau einem der folgenden Typen; neue Seiten müssen einem Typ entsprechen.

| Typ | Zweck | Aufbau |
|---|---|---|
| **Liste** | Eine Ebene gleichartiger Einträge | Symbolleiste (Suche/Filter) + Tabelle |
| **Baum** | Daten über mehrere Strukturebenen | Collapsible Tree (Abschnitt 13) |
| **Formular** | Anlegen/Bearbeiten genau einer Entität | Formular nach Abschnitt 12.3 |
| **Detail** | Lesende Ansicht einer Entität mit zugehörigen Daten | Kopfblock (Stammdaten + Aktionen) + untergeordnete Liste bzw. Baum |
| **Bestätigung** | Rückfrage vor dem Löschen/Statuswechsel | Abschnitt 12.4 |

### 11.3 Aktives Objekt

- Fast alle Daten hängen an einem `objekt`. Das aktive Objekt wird in der Session gehalten und filtert alle Listen/Bäume,
  die objektbezogen sind (Kosten, Verteilung, Zähler, Abrechnungen).
- Existiert genau ein Objekt, ist es automatisch aktiv und die Auswahl wird nicht angezeigt.
- „Objekte & Wohneinheiten“, „Eigentümer“, „Mieter“, „Zählertypen“ und „Benutzer“ sind objektübergreifend.

## 12. Einheitliches Muster für Erzeugen, Bearbeiten, Löschen

Dieses Muster gilt ausnahmslos für alle Entitäten, die im UI veränderbar sind (Matrix in 12.5).

### 12.1 URL-Schema

| Aktion | Methode & Pfad | Beispiel |
|---|---|---|
| Liste/Baum | `GET /<ressource>/` | `/mieter/` |
| Detail | `GET /<ressource>/<id>` | `/mieter/7` |
| Neu (Formular) | `GET /<ressource>/neu` | `/mieter/neu` |
| Neu (speichern) | `POST /<ressource>/neu` | |
| Bearbeiten (Formular) | `GET /<ressource>/<id>/bearbeiten` | `/mieter/7/bearbeiten` |
| Bearbeiten (speichern) | `POST /<ressource>/<id>/bearbeiten` | |
| Löschen (Bestätigung) | `GET /<ressource>/<id>/loeschen` | `/mieter/7/loeschen` |
| Löschen (ausführen) | `POST /<ressource>/<id>/loeschen` | |

Ressourcennamen (Plural, ohne Umlaute): `eigentuemer`, `objekte`, `wohneinheiten`, `mieter`, `mietverhaeltnisse`,
`zaehlertypen`, `zaehler`, `zaehlerstaende`, `verteilung` (= `objekt_kostenart_konfiguration`), `kosten`, `belege`,
`abrechnungen`, `benutzer`. Ein übergeordnetes Objekt wird beim Anlegen per Query-Parameter vorbelegt
(z. B. `/wohneinheiten/neu?objekt_id=3`).

### 12.2 Listen und Baumknoten: einheitliche Aktionen

- **Neu anlegen**: In Listen immer als primärer Button oben rechts („+ Neu anlegen“, bei Bezug mit Entitätsname, z. B.
  „+ Mieter anlegen“). In Bäumen als „+“-Aktion am **Elternknoten** („+ Wohneinheit“, „+ Mietverhältnis“ …), zusätzlich
  der primäre Button für die oberste Ebene.
- **Zeilen-/Knotenaktionen** stehen immer ganz rechts, immer in derselben Reihenfolge und mit denselben Symbolen:
  **Anzeigen (Auge) · Bearbeiten (Stift) · Löschen (Papierkorb, rot)**. Nicht verfügbare Aktionen werden ausgeblendet,
  nie durch andere Elemente ersetzt (Spalten bleiben ausgerichtet).
- Aktionen sind Buttons/Links mit Text-Tooltip (`title`) und für Screenreader beschriftet (`aria-label`).
- Ein Klick auf den Namen/Titel einer Zeile öffnet die Detailansicht.

### 12.3 Formulare

- **Ein Formular je Entität**, identisch für Anlegen und Bearbeiten (gleiches Template, gleiche Felder); der Seitentitel
  lautet „<Entität> anlegen“ bzw. „<Entität> bearbeiten“.
- Beschriftung über dem Feld; Pflichtfelder mit `*`; optionale Felder (`NULLABLE` laut Abschnitt 3) ohne Markierung.
- Felder in der Reihenfolge der Spalten aus Abschnitt 3, thematisch in Abschnitte (Fieldsets) gruppiert
  (z. B. Mieter: Person · Kontakt · Bankverbindung · Nachsendeadresse).
- **Buttons am Formularende, immer in dieser Reihenfolge**: „Speichern“ (primär) · „Abbrechen“ (sekundär, kehrt ohne
  Änderung zur Herkunftsseite zurück). Kein weiterer Button im Formular; „Löschen“ steht nie im Bearbeitungsformular,
  sondern nur als Aktion nach 12.2.
- Validierung erfolgt serverseitig; Fehler werden **am Feld** und als Zusammenfassung oberhalb des Formulars in deutscher
  Sprache angezeigt, bereits eingegebene Werte bleiben erhalten (HTTP 422, Formular erneut dargestellt).
- Nach erfolgreichem Speichern: Redirect auf die Herkunftsseite (Liste, Baum oder Detail) mit Erfolgsmeldung
  („Mieter „Mustermann“ wurde angelegt/gespeichert“); im Baum bleibt der betroffene Knoten aufgeklappt und wird hervorgehoben.
- Abhängige Auswahlfelder (z. B. Mieter bei Mietverhältnis) sind `<select>`-Felder; daneben führt der Link „Neu anlegen“
  zum Formular der jeweiligen Entität und danach zurück zum ursprünglichen Formular.

### 12.4 Löschen

- Löschen geschieht **immer in zwei Schritten**: Klick auf „Löschen“ öffnet eine Bestätigung (mit JavaScript als
  `<dialog>`, ohne JavaScript als eigene Bestätigungsseite `GET …/loeschen`); erst der Button „Endgültig löschen“
  (rot, `POST`, CSRF) führt aus. Die Bestätigung nennt Entität und Bezeichnung des Eintrags.
- Fremdschlüssel sind `ON DELETE RESTRICT` (Abschnitt 9). Wird ein Eintrag noch referenziert, wird **nicht** gelöscht;
  stattdessen erscheint eine Fehlermeldung mit den Abhängigkeiten („Wird noch verwendet von: 2 Mietverhältnisse“).
  Es gibt kein kaskadierendes Löschen und kein Soft-Delete.
- Löschen von Abrechnungen ist nur im Status `ENTWURF` möglich (siehe 14.9).

### 12.5 Entitäten-Matrix (was ist im UI veränderbar)

| Entität / Tabelle | Anlegen | Bearbeiten | Löschen | Hinweis |
|---|---|---|---|---|
| `eigentuemer` | ✔ | ✔ | ✔ | |
| `objekt` | ✔ | ✔ | ✔ | |
| `wohneinheit` | ✔ | ✔ | ✔ | |
| `mieter` | ✔ | ✔ | ✔ | Löschen nur ohne Mietverhältnisse |
| `mietverhaeltnis` | ✔ | ✔ | ✔ | Überschneidungsprüfung (14.4) |
| `zaehlertyp` | ✔ | ✔ | ✔ | Löschen nur ohne Zähler/Konfiguration, sonst „deaktivieren“ über Bearbeiten (`aktiv`) |
| `zaehler` | ✔ | ✔ | ✔ | Löschen nur ohne Zählerstände |
| `zaehlerstand` | ✔ (MANUELL) | ✔ nur `MANUELL` | ✔ nur `MANUELL` | Werte mit Quelle `SCHNITTSTELLE` sind schreibgeschützt |
| `objekt_kostenart_konfiguration` | ✔ | ✔ | ✔ | Löschen nur, wenn keine Abrechnung des betroffenen Zeitraums existiert |
| `kosten` | ✔ | ✔ | ✔ | Bearbeiten/Löschen gesperrt, wenn eine Abrechnung ab `FINALISIERT` das Jahr betrifft |
| `kosten_beleg` | ✔ (Upload) | – | ✔ | Ersetzen = löschen + neu hochladen |
| `abrechnung` | ✔ (Abrechnungslauf) | Status-Aktionen | ✔ nur `ENTWURF` | Siehe 14.9 |
| `benutzer` | ✔ | ✔ | ✔ | Nicht löschbar: sich selbst und der letzte aktive Benutzer |
| `kostenart`, `verteilerschluessel` | – | – | – | Fester Katalog, nur Anzeige |
| `kosten_jahresanteil` | – | – | – | Berechnet, nur Anzeige |
| `abrechnungsposition`, `abrechnungsposition_kostenart` | – | – | – | Vom Abrechnungslauf erzeugt, nur Anzeige (Vorauszahlung siehe 14.9) |

## 13. Collapsible Tree

Sobald Daten **über mehr als eine Strukturebene** dargestellt werden, wird ein Collapsible Tree verwendet; flache,
gleichartige Daten (eine Ebene) werden als Tabelle dargestellt.

### 13.1 Verhalten und Aufbau

- Umsetzung mit den nativen Elementen `<details>`/`<summary>` (funktioniert ohne JavaScript, tastaturbedienbar,
  zugänglich). Jeder Knoten ist eine Zeile mit festen, ausgerichteten Bereichen:

  `[Auf-/Zuklappen] [Typ-Symbol] Titel │ Kennwerte (Spalten) │ Status-Badges │ Aktionen (12.2)`

- Standardzustand: Ebene 1 aufgeklappt, tiefere Ebenen zugeklappt. Über der Struktur stehen „Alle aufklappen“ /
  „Alle zuklappen“. Optional merkt sich JavaScript den Zustand je Seite im Browser (`localStorage`).
- Blattknoten haben dieselbe Zeilenstruktur ohne Auf-/Zuklapp-Symbol.
- Knotentypen unterscheiden sich nur durch Symbol und Kennwerte, nicht durch Layout; Einrückung je Ebene einheitlich.
- Leere Ebenen zeigen einen Hinweis („Noch keine Wohneinheiten“) mit der passenden „+“-Aktion.
- Große Datenmengen (z. B. tägliche Zählerstände) werden **nicht** als Knoten dargestellt, sondern als Blattknoten
  „Zählerstände (n)“, der auf die paginierte Tabelle verweist.

### 13.2 Bäume im System

| Seite | Struktur (Ebene 1 → …) |
|---|---|
| Objekte & Wohneinheiten | Eigentümer → Objekt → Wohneinheit → Mietverhältnis (inkl. Leerstandszeiträume, nur lesend) |
| Zähler & Zählerstände | Objekt → Wohneinheit bzw. „Objektweit“ → Zähler → „Zählerstände (n)“ |
| Verteilung | Objekt → Kostenart (alle 17, auch unkonfigurierte) → Konfigurationsversion (`gueltig_ab`/`gueltig_bis`) |
| Kostenpositionen | Objekt → Rechnungsjahr → Kostenart → Kostenposition → Belege / Jahresanteile |
| Abrechnungen | Objekt → Abrechnung (Jahr) → Abrechnungsposition (Mietverhältnis) → Kostenart-Detailzeile |

## 14. Seiten im Detail

### 14.1 Anmeldung
- `GET/POST /login`: Benutzername oder E-Mail + Passwort; Fehlermeldung bewusst allgemein („Anmeldedaten ungültig“).
- `POST /logout`. Inaktive Benutzer (`aktiv = false`) können sich nicht anmelden. `letzter_login` wird gesetzt.
- Nicht angemeldete Zugriffe werden auf `/login` umgeleitet (mit Rücksprung nach der Anmeldung).
- Passwort ändern über das Benutzermenü (aktuelles + neues Passwort); Passwort-Hashing wie in 8.1.

### 14.2 Übersicht (`/`)
- Je Objekt eine Karte mit Kennzahlen: Anzahl Wohneinheiten, aktive Mietverhältnisse, aktueller Leerstand, Status der
  Abrechnung des Vorjahres. Darunter Hinweise (z. B. „Abrechnung 2025 ist noch im Entwurf“). Jede Kennzahl verlinkt auf
  die zugehörige Seite. Keine Eingaben auf dieser Seite.

### 14.3 Eigentümer, Objekte & Wohneinheiten
- Baum nach 13.2. Aktionen: Eigentümer „+ Objekt“; Objekt „+ Wohneinheit“; Wohneinheit „+ Mietverhältnis“.
- Wohneinheit-Detail: Stammdaten (Typ, Wohnfläche, MEA, verfügbar ab), Mietverhältnisse chronologisch, Zähler.
- Eigentümer werden zusätzlich unter „Eigentümer“ als Liste gepflegt (Formular nach 12.3); der Baum nutzt dieselben Formulare.
- Formularfelder: je Spalte laut 3.1–3.3; `typ` als Auswahl (Wohnung/Gewerbe).

### 14.4 Mieter & Mietverhältnisse
- Mieter: Liste (eine Ebene, daher kein Baum) mit Name, Kontakt, aktuellem Mietverhältnis und Suche; Detail zeigt Stammdaten, Nachsendeadresse und alle
  Mietverhältnisse (Tabelle).
- Mietverhältnis-Formular: Wohneinheit, Mieter, Einzugsdatum, Auszugsdatum (leer = laufend), Personenanzahl. Anlegen
  vom Wohneinheit-Knoten (Wohneinheit vorbelegt) oder vom Mieter (Mieter vorbelegt).
- Validierungen: Auszug ≥ Einzug; **keine zeitliche Überschneidung** mit einem anderen Mietverhältnis derselben Wohneinheit
  (Fehler nennt das kollidierende Mietverhältnis); Einzug nicht vor `verfuegbar_ab` der Wohneinheit (Hinweis, kein Fehler).
- **Leerstand** wird im Wohneinheit-Baum als berechneter, nicht editierbarer Knoten „Leerstand von – bis“ angezeigt
  (Regel 3.5); er hat keine Aktionen.

### 14.5 Zählertypen, Zähler & Zählerstände
- Zählertypen: Liste (Bezeichnung, Einheit, aktiv), Formular nach 12.3.
- Zähler: Baum nach 13.2; Formular mit Zählertyp, Zuordnung (Wohneinheit **oder** Objekt, mindestens eins; Auswahl als
  zwei Auswahlfelder), externe Geräte-ID, Ein-/Ausbaudatum.
- Zählerstände eines Zählers: paginierte Tabelle (absteigend nach Datum) mit Filter Zeitraum; Quelle als Badge
  (Schnittstelle/Manuell). „+ Zählerstand erfassen“ legt `MANUELL` an; existiert für den Tag bereits ein Wert, wird
  der Fehler „Für dieses Datum existiert bereits ein Zählerstand“ gezeigt (Eindeutigkeit 3.11).
  Der Datenimport erfolgt ausschließlich über die Schnittstelle (Abschnitt 5), nicht über das UI.

### 14.6 Verteilung (Konfiguration je Kostenart)
- Baum nach 13.2 mit allen 17 Kostenarten je Objekt; nicht konfigurierte Kostenarten sind mit Badge „nicht konfiguriert“
  und „+ Konfiguration“ markiert.
- Formular: Kostenart (vorbelegt, nicht änderbar), Verteilerschlüssel, „verbrauchsabhängig“, Grundkostenanteil in %
  (nur sichtbar/verpflichtend, wenn verbrauchsabhängig mit Split), Zählertyp (nur bei verbrauchsabhängig), gültig ab/bis.
- Validierungen: `verbrauchsabhaengig_moeglich` der Kostenart beachten; Schlüssel `VERBRAUCH` nur mit Zählertyp;
  Grundkostenanteil 0–100; keine Überschneidung der Gültigkeit je Objekt und Kostenart.

### 14.7 Kostenpositionen
- Baum nach 13.2. „+ Kostenposition“ auf Ebene Kostenart oder Jahr (Kostenart vorbelegt).
- Formular: Kostenart, Betrag, Rechnungsdatum, Leistungszeitraum von/bis, Abgrenzungsart (mit kurzer Erklärung je
  Option), Lieferant, Beschreibung. Bei `PERIODENGERECHT_ZAEHLERSTAND` zusätzlich Auswahl des Stichtags-Zählerstands.
- Detail: Stammdaten, **Belege** (Liste mit Upload-Feld, Download, Löschen; Speicherung nach 8.5) und **Jahresanteile**
  (nur Anzeige, Berechnungsgrundlage im Klartext).

### 14.8 Kostenarten (nur Ansicht)
- Liste der 17 Positionen aus 3.6 mit Kennzeichen „verbrauchsabhängig möglich“; ohne Anlegen/Bearbeiten/Löschen.

### 14.9 Abrechnungen
- Baum nach 13.2. „+ Abrechnung“ startet den Abrechnungslauf: Auswahl Objekt und Abrechnungsjahr (eindeutig je Objekt,
  3.15). Auf der folgenden Seite werden je Mietverhältnis die **Vorauszahlungen als Jahresbetrag** erfasst
  (Tabelle mit einem Eingabefeld je Zeile, vgl. Abschnitt 1, „Vorauszahlungen“); erst danach wird die Abrechnung erzeugt.
- Status-Aktionen (jeweils mit Bestätigung 12.4): `ENTWURF → FINALISIERT → VERSENDET`; Rückschritt von `FINALISIERT` nach
  `ENTWURF` ist erlaubt, ab `VERSENDET` nicht. Löschen nur im Status `ENTWURF`. Vorauszahlungen sind nur im Status
  `ENTWURF` änderbar (Aktion „Bearbeiten“ an der Abrechnungsposition).
- Die Berechnung selbst (Umlage, Nutzungstage, Saldo, Rundung) gehört zur Berechnungs-Engine (Abschnitt 6); das UI
  zeigt deren Ergebnis. Die PDF-/Druckansicht ist Folgephase.

### 14.10 Benutzer
- Liste (Benutzername, E-Mail, aktiv, letzter Login), Formular nach 12.3 (Passwort beim Anlegen Pflicht, beim Bearbeiten
  optional). Einschränkungen siehe 12.5.

## 15. Formulare, Tabellen und Texte: gemeinsame Regeln

- **Tabellen**: Kopfzeile fix, Zahlen rechtsbündig, Text linksbündig, Aktionsspalte ganz rechts ohne Überschrift-Text
  („Aktionen“ nur für Screenreader). Standardsortierung je Liste fachlich sinnvoll (Name, Datum absteigend …). Listen mit
  mehr als 25 Zeilen werden paginiert.
- **Enumerationswerte** werden mit deutschen Bezeichnungen angezeigt:

  | Wert | Anzeige |
  |---|---|
  | `WOHNUNG` / `GEWERBE` | Wohnung / Gewerbe |
  | `SCHNITTSTELLE` / `MANUELL` | Schnittstelle / Manuell |
  | `ABFLUSSPRINZIP` | Abflussprinzip |
  | `PERIODENGERECHT_TAGESGENAU` | Periodengerecht (tagesgenau) |
  | `PERIODENGERECHT_ZAEHLERSTAND` | Periodengerecht (Zählerstand) |
  | `ENTWURF` / `FINALISIERT` / `VERSENDET` | Entwurf / Finalisiert / Versendet |

- **Status-Badges** verwenden ausschließlich die Farbklassen aus 17.3 (Erfolg, Hinweis, Fehler, Neutral).
- **Meldungstexte** sind formelhaft und einheitlich: „<Entität> „<Bezeichnung>“ wurde angelegt / gespeichert / gelöscht.“
- **Leerzustände**, **Fehlerseiten** (403, 404, 500) und die Anmeldeseite nutzen dasselbe Layout und dieselben CSS-Klassen.

## 16. Technische Umsetzung des UI

- Pro Funktionsbereich ein Blueprint (`stammdaten`, `zaehler`, `kosten`, `abrechnung`, `auth` …, vgl. Projektrichtlinien).
- Templates unter `app/templates/`: ein Basis-Template `base.html` und **gemeinsame Makros** für alle wiederkehrenden Elemente
  (`macros/forms.html`, `macros/tables.html`, `macros/tree.html`, `macros/actions.html`, `macros/icons.html`); Seiten
  bauen ausschließlich aus diesen Makros auf, damit 12 und 13 technisch erzwungen einheitlich sind.
- Gemeinsame CRUD-Basis (Hilfsklasse/Funktionen) für Liste, Neu, Bearbeiten, Löschen inklusive Abhängigkeitsprüfung,
  Redirect und Flash-Meldungen; entitätsspezifisch bleiben nur Formularfelder, Validierung und Spaltendefinition.
- Icons als SVG-Sprite (`static/img/icons.svg`), eingebunden ausschließlich über das Icon-Makro.
- Formulare mit CSRF-Schutz (Flask-WTF `CSRFProtect`, Annahme A3 in Abschnitt 19).

## 17. Zentrales Design (eine CSS-Datei)

### 17.1 Regeln
- Alle Gestaltung steckt in **einer** Datei `app/static/css/app.css`. Verboten sind: `style`-Attribute, `<style>`-Blöcke,
  weitere CSS-Dateien pro Seite, CSS-Frameworks oder CDN-Einbindungen.
- Farben, Abstände, Schriftgrößen, Radien und Schatten sind **Design-Tokens** (CSS Custom Properties in `:root`); im
  restlichen CSS werden nur Tokens verwendet, keine Rohwerte. Eine Änderung des Erscheinungsbilds erfolgt allein über die Tokens.
- Gestaltung erfolgt über **Komponentenklassen** (BEM-nahe, sprechende Namen); Templates setzen nur Klassen.
- Systemschriftart (kein Webfont), Basisschrift 16 px, ausreichender Kontrast (WCAG AA), sichtbarer Fokusrahmen,
  Bedienung per Tastatur vollständig möglich.
- Desktop-first (ab 1024 px Breite optimiert); bei schmalerer Anzeige klappt die Navigation ein und Tabellen scrollen
  horizontal. Kein Dark Mode in der ersten Ausbaustufe.

### 17.2 Tokens (Auszug)

| Gruppe | Tokens |
|---|---|
| Farben | `--color-primary`, `--color-primary-contrast`, `--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-success`, `--color-warning`, `--color-danger`, `--color-info` |
| Abstände | `--space-1` … `--space-6` (4 px-Raster) |
| Schrift | `--font-family`, `--font-size-sm`, `--font-size-base`, `--font-size-lg`, `--font-size-xl` |
| Form | `--radius`, `--shadow-1`, `--border-width`, `--tree-indent` |

### 17.3 Komponenten (Klassenkatalog)

| Komponente | Klassen |
|---|---|
| Seitengerüst | `.app`, `.app__header`, `.app__nav`, `.app__main`, `.breadcrumb`, `.page-header`, `.page-header__title`, `.page-header__actions` |
| Buttons | `.btn`, `.btn--primary`, `.btn--secondary`, `.btn--danger`, `.btn--icon` |
| Aktionsleiste | `.actions` (Zeilen-/Knotenaktionen in fester Reihenfolge 12.2) |
| Tabellen | `.table`, `.table__num`, `.table__actions` |
| Formulare | `.form`, `.form__section`, `.form__field`, `.form__label`, `.form__error`, `.form__hint`, `.form__actions` |
| Baum | `.tree`, `.tree__node`, `.tree__summary`, `.tree__title`, `.tree__meta`, `.tree__badges`, `.tree__actions`, `.tree__children`, `.tree__empty` |
| Rückmeldung | `.flash`, `.flash--success`, `.flash--warning`, `.flash--error`, `.badge`, `.badge--success`, `.badge--warning`, `.badge--danger`, `.badge--neutral` |
| Sonstiges | `.card`, `.toolbar`, `.dialog`, `.pagination`, `.test-banner` |

## 18. Testmodus und UI-Tests

### 18.1 Testmodus
- Der Testmodus betreibt die Anwendung **statt auf der Live-Datenbank auf einer Test-Datenbank gleicher Struktur**:
  Datenbankname `<database.name>_test` (also `texxem_test`), gleicher Host und gleiche Zugangsdaten aus `config.json`
  (keine zweite Konfigurationsdatei, vgl. 8.2).
- **Gleiche Struktur** ist dadurch garantiert, dass die Testdatenbank ausschließlich über dieselben Alembic-Migrationen
  (inklusive Seed-Daten für `kostenart`, `verteilerschluessel`, `zaehlertyp`) aufgebaut wird wie die Live-Datenbank.
- Aktivierung über `create_app(test_mode=True)`. Zum manuellen Ausprobieren dient der Einstiegspunkt `wsgi_test.py`
  (`flask --app wsgi_test db upgrade`, dann `flask --app wsgi_test run`), nur lokal und nicht als systemd-Dienst. Der
  produktive Dienst (8.6) läuft nie im Testmodus.
- **Schutzmechanismen**: Der Testmodus fragt nach dem Verbindungsaufbau `SELECT DATABASE()` ab und bricht beim Start
  ab, wenn der Name nicht auf `_test` endet; der Upload-Ordner im Testmodus ist ein separates Verzeichnis
  (`uploads/_test/`), Logdateien heißen `app_<Zeitstempel>_test.log` (eigene Aufbewahrung von 5 Dateien, unabhängig
  von den Live-Logs). In der Oberfläche erscheint das Banner „TESTMODUS – Testdatenbank“ (11.1).
- Die Testdatenbank `texxem_test` muss existieren und für den konfigurierten Datenbankbenutzer vollständig zugänglich sein
  (Einrichtung: `CREATE DATABASE texxem_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;` und `GRANT ALL ON texxem_test.*`).
- Die Testdatenbank wird zu Beginn jedes Testlaufs frisch aufgebaut (Migration `downgrade base` → `upgrade`) und
  zwischen einzelnen Tests auf den Seed-Stand zurückgesetzt (alle Nicht-Katalog-Tabellen geleert).

### 18.2 Test-Cases
- Test-Cases interagieren **so weit wie möglich über das Web-Interface** mit der Anwendung (Flask-Testclient:
  Anmeldung, Formulare mit CSRF-Token ausfüllen und absenden, Redirects verfolgen, Löschbestätigungen auslösen). Direkte
  Datenbankzugriffe sind nur zulässig für: Testvorbereitung, die im UI nicht möglich ist (Seed von `SCHNITTSTELLE`-Zählerständen,
  da kein Import-UI existiert), und die **Verifikation**.
- **Jeder Test verifiziert das Ergebnis in der Datenbank** (unabhängige Abfrage nach der UI-Aktion): Zeile vorhanden/geändert/
  gelöscht, Werte, Fremdschlüssel, Zeitstempel – zusätzlich zur Prüfung der HTML-Antwort (Meldung, Weiterleitung).
- Abdeckung je Entität laut Matrix 12.5: Anlegen, Bearbeiten, Löschen (Erfolg), Validierungsfehler (nichts in der
  Datenbank geändert), Löschen mit Abhängigkeit (Eintrag bleibt bestehen), schreibgeschützte Entitäten (Aktion nicht
  angeboten, direkter `POST` wird abgewiesen), Zugriff ohne Anmeldung (Redirect auf `/login`), fehlendes CSRF-Token (400).
- Zusätzlich je Querschnittsregel: einheitliche Aktionen und Buttons (12.2/12.3) in Liste und Baum, Baumstruktur
  (13.2), Überschneidungsprüfung von Mietverhältnissen, Eindeutigkeit von Zählerständen, Status-Übergänge der Abrechnung.
- Ablauf-/Szenariotests über mehrere Seiten (z. B. Eigentümer → Objekt → Wohneinheit → Mieter → Mietverhältnis →
  Zähler → Kostenposition → Abrechnung anlegen), Verifikation am Ende in der Datenbank.
- Ein Strukturvergleich (Spalten, Indizes, Fremdschlüssel, CHECK-Constraints, Tabellen, Seed-Daten) zwischen Live- und
  Testdatenbank stellt sicher, dass beide exakt gleich aufgebaut sind; ein weiterer Test belegt, dass UI-Änderungen im
  Testmodus die Live-Datenbank nicht berühren.
- Querschnittstests prüfen die Einheitlichkeit des UI: gleiche Formular-Buttons, gleiche Aktionsreihenfolge in Listen
  und Bäumen, Baum für mehrstufige und Tabelle für einstufige Daten, genau ein Stylesheet ohne Inline-Styles, jede
  verwendete CSS-Klasse ist in `app.css` definiert, keine Roh-Farbwerte außerhalb der Design-Tokens.
- Browser-Tests mit JavaScript (Dialog, Zustand des Baums) sind optional und kein Bestandteil der ersten Ausbaustufe.

## 19. Annahmen zu Phase 2 (zur Bestätigung)

| Nr. | Annahme |
|---|---|
| A1 | Es kann mehrere Objekte geben; das „aktive Objekt“ (11.3) filtert objektbezogene Seiten. |
| A2 | Alle UI-Texte sind ausschließlich Deutsch; keine Mehrsprachigkeit. |
| A3 | CSRF-Schutz über Flask-WTF (`CSRFProtect`); weitere Flask-WTF-Funktionen (Formularklassen) werden nicht vorausgesetzt. |
| A4 | Löschen ist immer endgültig (kein Papierkorb/Soft-Delete); Schutz vor Datenverlust ausschließlich über Bestätigung und `RESTRICT`. |
| A5 | `benutzer` darf mehrere Konten haben, alle mit denselben Rechten (eine Rolle, vgl. Abschnitt 6). |
| A6 | Zählerstände mit Quelle `SCHNITTSTELLE` sind im UI nicht änderbar; manuelle Werte dürfen den Tageswert einer Schnittstelle nicht überschreiben (Eindeutigkeit 3.11). |
| A7 | Kostenpositionen und Verteilung sind nach Finalisierung einer betroffenen Abrechnung gesperrt (12.5). |
| A8 | Paginierung ab 25 Zeilen; Suche/Filter nur dort, wo in 14 genannt. |
| A9 | Kein Dark Mode, kein Druck-/PDF-Layout, keine Mehrbenutzer-Rechtedifferenzierung in dieser Phase. |
| A10 | Die Testdatenbank `texxem_test` ist ausschließlich für Tests vorgesehen und darf jederzeit geleert werden. |

## 20. Umsetzungsstand Phase 2

Umgesetzt sind der Testmodus (Abschnitt 18), die UI-Grundlagen (Abschnitte 10–13, 15–17) und die Seiten aus Abschnitt 14.
Folgende technische Festlegungen und Abweichungen gelten:

| Thema | Festlegung |
|---|---|
| Formularfelder | Namen der Eingabefelder entsprechen den Spaltennamen des Schemas (z. B. `einzugsdatum`, `wohnflaeche_m2`); das Passwortfeld der Benutzerverwaltung heißt `passwort` |
| Passwort | Mindestlänge 8 Zeichen (Benutzerverwaltung und „Passwort ändern“) |
| Anmeldung | Benutzername oder E-Mail; der erste Benutzer wird über `flask --app wsgi create-user <benutzername> <email>` angelegt |
| Löschbestätigung (12.4) | Umgesetzt als eigene Bestätigungsseite (Variante ohne JavaScript); der optionale `<dialog>` entfällt, die Seiten enthalten kein JavaScript |
| Baumzustand (13.1) | „Alle aufklappen/zuklappen“ und das Aufklappen des gespeicherten Knotens erfolgen serverseitig über `?expand=all\|none` und `?open=<knoten-id>`; kein `localStorage` |
| Beleg-Aktion „Anzeigen“ | lädt die Datei herunter (`/belege/<id>/download`); Belege besitzen keine Detailseite |
| Kostenposition (14.7) | Die Auswahl des Stichtags-Zählerstands entfällt im Formular; sie gehört zum Jahresanteil (`kosten_jahresanteil.referenz_zaehlerstand_id`) und wird von der Berechnungs-Engine gesetzt. Zusätzlich darf der Betrag nicht 0 sein (Gutschriften mit negativem Betrag sind erlaubt) |
| Abrechnungslauf (14.9) | Umgesetzt sind Anlegen (Objekt + Jahr), Statuswechsel mit Bestätigung, Löschen im Entwurf sowie die Baum-/Detailansicht der Positionen. Das Erzeugen der Positionen samt Erfassung der Vorauszahlungen setzt die Berechnungs-Engine voraus (Abschnitt 6) und ist noch nicht umgesetzt |
| Gesperrte Kosten (A7) | Eine Kostenposition ist gesperrt, sobald für das Objekt eine Abrechnung im Status `FINALISIERT`/`VERSENDET` für das Rechnungsjahr oder ein Jahr des Leistungszeitraums existiert |
| Benutzer | Eigenes Konto nicht löschbar; der letzte aktive Benutzer kann weder gelöscht noch deaktiviert werden |
| Zählertypen | Löschen nur ohne Verwendung; sonst über `aktiv` deaktivieren |
