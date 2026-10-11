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
- Authentifizierung (z. B. API-Key) und genaues Zielformat werden in Phase 2 (API-Spezifikation) definiert.

## 6. Offen für Folgephasen

- API-/Business-Logik-Spezifikation (Berechnungs-Engine im Detail, Rundungsregeln)
- UI/Screens (Erfassung Objekte, Wohneinheiten, Mieter, Kosten, Abrechnungslauf)
- Druckvorlage/PDF-Layout der Abrechnung
- Authentifizierung/Rechteverwaltung für `benutzer` im Detail
- Konkretes Schnittstellenformat/-protokoll mit der externen Messapplikation

## 7. Getroffene Annahmen (zur Bestätigung)

- Währung ausschließlich EUR (keine Mehrwährungsfähigkeit).
- Jede Kostenposition betrifft genau ein Objekt (keine geteilten Kosten über mehrere Objekte/Wirtschaftseinheiten hinweg).
- Keine Überschneidung zweier Mietverhältnisse derselben Wohneinheit (wird anwendungsseitig verhindert).
