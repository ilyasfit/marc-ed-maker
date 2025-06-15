import re
from urllib.parse import urlparse

def load_list_from_file(filepath: str) -> set:
    """Liest jede Zeile aus einer Datei und gibt sie als Set von Strings zurück."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Entfernt Leerzeichen und ignoriert leere Zeilen
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        print(f"WARNUNG: Datei nicht gefunden: {filepath}. Eine leere Liste wird verwendet.")
        return set()

def contains_forbidden_link(message_content: str, whitelisted_domains: set) -> bool:
    """
    Überprüft, ob die Nachricht einen Link enthält, dessen Domain nicht auf der Whitelist steht.
    
    Returns:
        True, wenn ein verbotener Link gefunden wurde, sonst False.
    """
    # Ein Regex, um URLs und Domain-Namen zu finden.
    # Dieser Regex verhindert, dass ungültige Domain-Namen wie "hoje....na" erkannt werden,
    # indem er sicherstellt, dass Punkte von alphanumerischen Zeichen gefolgt werden.
    url_pattern = re.compile(r'https?://[^\s/$.?#].[^\s]*|[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}')
    found_urls = url_pattern.findall(message_content)

    if not found_urls:
        return False

    for url in found_urls:
        # Wenn es keine URL ist, dann fügen wir das Protokoll hinzu, um es für urlparse nutzbar zu machen
        if not url.startswith('http'):
            url = 'http://' + url
        try:
            # Extrahiere den Domain-Namen (z.B. 'tradingview.com')
            domain = urlparse(url).netloc
            # Entferne 'www.' für einen einfacheren Vergleich
            if domain.startswith('www.'):
                domain = domain[4:]
            
            is_whitelisted = False
            for whitelisted_domain in whitelisted_domains:
                if domain == whitelisted_domain or domain.endswith('.' + whitelisted_domain):
                    is_whitelisted = True
                    break
            
            if not is_whitelisted:
                # Sobald ein nicht erlaubter Link gefunden wird, können wir abbrechen.
                return True
        except Exception:
            # Ignoriere ungültige URLs
            continue
    
    return False

def find_forbidden_content(message_content: str, forbidden_words: set) -> str | None:
    """
    Überprüft die Nachricht auf verbotene Wörter.
    
    Returns:
        Eine Zeichenkette mit dem Grund, wenn ein Verstoß gefunden wurde, sonst None.
    """
    content_lower = message_content.lower()

    # Verbotene Wörter/Phrasen prüfen
    for phrase in forbidden_words:
        # Wir verwenden \b, um sicherzustellen, dass wir nur ganze Wörter matchen.
        # re.escape ist wichtig, falls die Phrasen Sonderzeichen enthalten.
        pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
        if re.search(pattern, content_lower):
            return "Uso de linguagem/tópico proibido"
    
    return None
