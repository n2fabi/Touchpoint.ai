# Filter definieren
from datetime import datetime
from bs4 import BeautifulSoup

def datetimeformat(value, format='%d.%m.%Y %H:%M'):
    """Wandelt einen Timestamp oder datetime in ein lesbares Format um."""
    if isinstance(value, (int, float)):  # Unix timestamp
        value = datetime.fromtimestamp(value)
    elif isinstance(value, str):  # falls als ISO-String gespeichert
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value  # einfach zurückgeben, wenn nicht parsbar
    return value.strftime(format)

from markupsafe import Markup, escape
import re


def nl2p(value):
    """Wandelt doppelte Zeilenumbrüche in Absätze (<p>) um, ohne zusätzliche <br>."""
    if not value:
        return ""

    value = value.strip()
    paragraphs = re.split(r'\n\s*\n', value)  # Absätze anhand leerer Zeilen trennen

    html_parts = []
    for p in paragraphs:
        safe_p = escape(p.strip())
        html_parts.append(f"<p>{safe_p}</p>")

    return Markup("".join(html_parts))

import re

def normalize_html_for_editor(html: str) -> str:
    """
    Normalize font-family declarations in inline styles so TinyMCE
    can render them consistently without breaking the HTML.
    """
    if not html:
        return ""

    # Bekannte Fonts mit sauberen Fallbacks
    fallbacks = {
        "arial": "Arial, Helvetica, sans-serif",
        "arial black": "'Arial Black', Gadget, sans-serif",
        "comic sans ms": "'Comic Sans MS', cursive, sans-serif",
        "courier new": "'Courier New', Courier, monospace",
        "georgia": "Georgia, serif",
        "impact": "Impact, Charcoal, sans-serif",
        "tahoma": "Tahoma, Geneva, sans-serif",
        "times new roman": "'Times New Roman', Times, serif",
        "trebuchet ms": "'Trebuchet MS', Helvetica, sans-serif",
        "verdana": "Verdana, Geneva, sans-serif",
    }

    # Ersetzer-Funktion für regex
    def replace_font(match):
        fam = match.group(2).strip().strip('"').strip("'")
        fam_lower = fam.lower()
        if fam_lower in fallbacks:
            return f"font-family: {fallbacks[fam_lower]};"
        else:
            # Falls unbekannter Font: Original + generischer Fallback
            primary = f"'{fam}'" if " " in fam else fam
            return f"font-family: {primary}, sans-serif;"

    # Regex: fängt font-family: "Name" / 'Name' / Name ein
    cleaned = re.sub(
        r"font-family\s*:\s*(['\"]?)([A-Za-z0-9 \-]+)\1\s*;?",
        replace_font,
        html,
        flags=re.IGNORECASE
    )
    print(cleaned)
    return cleaned
