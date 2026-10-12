"""German labels for tables and enum values."""

ENUM_LABELS = {
    "WOHNUNG": "Wohnung",
    "GEWERBE": "Gewerbe",
    "SCHNITTSTELLE": "Schnittstelle",
    "MANUELL": "Manuell",
    "ABFLUSSPRINZIP": "Abflussprinzip",
    "PERIODENGERECHT_TAGESGENAU": "Periodengerecht (tagesgenau)",
    "PERIODENGERECHT_ZAEHLERSTAND": "Periodengerecht (Zählerstand)",
    "ENTWURF": "Entwurf",
    "FINALISIERT": "Finalisiert",
    "VERSENDET": "Versendet",
}

# table name -> (singular, plural)
TABLE_LABELS = {
    "eigentuemer": ("Eigentümer", "Eigentümer"),
    "objekt": ("Objekt", "Objekte"),
    "wohneinheit": ("Wohneinheit", "Wohneinheiten"),
    "mieter": ("Mieter", "Mieter"),
    "mietverhaeltnis": ("Mietverhältnis", "Mietverhältnisse"),
    "kostenart": ("Kostenart", "Kostenarten"),
    "verteilerschluessel": ("Verteilerschlüssel", "Verteilerschlüssel"),
    "zaehlertyp": ("Zählertyp", "Zählertypen"),
    "objekt_kostenart_konfiguration": ("Verteilungskonfiguration", "Verteilungskonfigurationen"),
    "zaehler": ("Zähler", "Zähler"),
    "zaehlerstand": ("Zählerstand", "Zählerstände"),
    "kosten": ("Kostenposition", "Kostenpositionen"),
    "kosten_jahresanteil": ("Jahresanteil", "Jahresanteile"),
    "kosten_beleg": ("Beleg", "Belege"),
    "abrechnung": ("Abrechnung", "Abrechnungen"),
    "abrechnungsposition": ("Abrechnungsposition", "Abrechnungspositionen"),
    "abrechnungsposition_kostenart": ("Abrechnungszeile", "Abrechnungszeilen"),
    "benutzer": ("Benutzer", "Benutzer"),
}


def count_label(table: str, count: int) -> str:
    singular, plural = TABLE_LABELS.get(table, (table, table))
    return f"{count} {singular if count == 1 else plural}"
