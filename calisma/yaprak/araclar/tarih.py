from datetime import date, timedelta


def gun_farki(a, b):
    """Iki tarih arasindaki gun sayisini dondurur (isaret: a > b ise pozitif)."""
    return (a - b).days


def ay_basi(t):
    """Verilen tarihin ait oldugu ayin ilk gunu tarihini dondurur."""
    return date(t.year, t.month, 1)


def hafta_no(t):
    """Tarihin ISO hafta numarasini dondurur."""
    return t.isocalendar()[1]
