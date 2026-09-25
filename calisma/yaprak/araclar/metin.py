import re


def kirp(metin, n):
    """Metni n karaktere kirpip gerekirse '...' ekle."""
    if len(metin) <= n:
        return metin
    return metin[:n] + '...'


def slug(metin):
    """Metni kucuk harfe cevirip boslu/ozel karakterleri '-' ile degistir."""
    metin = metin.lower()
    metin = re.sub(r'[^a-z0-9]+', '-', metin)
    metin = metin.strip('-')
    return metin


def kelime_say(metin):
    """Bosluklara gore kelime sayar."""
    if not metin or not metin.strip():
        return 0
    return len(metin.split())
