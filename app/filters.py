# Filter definieren
from datetime import datetime
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

