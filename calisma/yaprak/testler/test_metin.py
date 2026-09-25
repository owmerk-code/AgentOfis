import pytest
from araclar.metin import kirp, slug, kelime_say


class TestKirp:
    def test_kisa_metin(self):
        assert kirp("merhaba", 10) == "merhaba"

    def test_sinir(self):
        assert kirp("merhaba", 7) == "merhaba"

    def test_uzun_metin(self):
        assert kirp("merhaba dunya", 5) == "merha..."

    def test_bos_metin(self):
        assert kirp("", 5) == ""


class TestSlug:
    def test_normal_metin(self):
        assert slug("Merhaba Dunya") == "merhaba-dunya"

    def test_ozel_karakterler(self):
        assert slug("Test-123!@#") == "test-123"

    def test_bos_metin(self):
        assert slug("") == ""

    def test_sadece_ozel_karakterler(self):
        assert slug("!@#$%") == ""


class TestKelimeSay:
    def test_tek_kelime(self):
        assert kelime_say("merhaba") == 1

    def test_birden_fazla_kelime(self):
        assert kelime_say("merhaba dunya nasil") == 3

    def test_bos_metin(self):
        assert kelime_say("") == 0

    def test_sadece_bosluk(self):
        assert kelime_say("   ") == 0

    def test_fazla_bosluk(self):
        assert kelime_say("bir   iki    uc") == 3
