import pytest
from datetime import date
from araclar.tarih import gun_farki, ay_basi, hafta_no


class TestGunFarki:
    def test_ayni_tarih(self):
        d = date(2024, 1, 15)
        assert gun_farki(d, d) == 0

    def test_bir_gun_farki(self):
        d1 = date(2024, 1, 16)
        d2 = date(2024, 1, 15)
        assert gun_farki(d1, d2) == 1

    def test_negatif_farki(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 16)
        assert gun_farki(d1, d2) == -1

    def test_ay_gecisi(self):
        d1 = date(2024, 2, 1)
        d2 = date(2024, 1, 31)
        assert gun_farki(d1, d2) == 1

    def test_yil_gecisi(self):
        d1 = date(2024, 1, 1)
        d2 = date(2023, 12, 31)
        assert gun_farki(d1, d2) == 1


class TestAyBasi:
    def test_ay_ortasi(self):
        result = ay_basi(date(2024, 1, 15))
        assert result == date(2024, 1, 1)

    def test_ay_ilk_gunu(self):
        result = ay_basi(date(2024, 1, 1))
        assert result == date(2024, 1, 1)

    def test_ay_son_gunu(self):
        result = ay_basi(date(2024, 1, 31))
        assert result == date(2024, 1, 1)

    def test_subat(self):
        result = ay_basi(date(2024, 2, 15))
        assert result == date(2024, 2, 1)

    def test_aralik(self):
        result = ay_basi(date(2024, 12, 25))
        assert result == date(2024, 12, 1)


class TestHaftaNo:
    def test_yil_baslas(self):
        result = hafta_no(date(2024, 1, 1))
        assert result == 1

    def test_normal_hafta(self):
        result = hafta_no(date(2024, 1, 15))
        assert result == 3

    def test_yil_sonu(self):
        result = hafta_no(date(2024, 12, 30))
        assert result == 1

    def test_yil_ortasi(self):
        result = hafta_no(date(2024, 6, 15))
        assert result == 24
