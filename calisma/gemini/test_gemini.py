import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ofis.motor.tip import Motor, MotorOlayi, MotorHatasi
from gemini.gemini import GeminiMotoru


class TestGeminiMotoru:
    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Her test için GEMINI_API_KEY ortam değişkenini set et"""
        os.environ["GEMINI_API_KEY"] = "test-key-12345"
        yield
        os.environ.pop("GEMINI_API_KEY", None)

    def test_motor_turu(self):
        """GeminiMotoru Motor'dan türüyor"""
        motor = GeminiMotoru()
        assert isinstance(motor, Motor)

    def test_motor_ozelikleri(self):
        """Motor özellikleri doğru"""
        motor = GeminiMotoru()
        assert motor.ad == "gemini"
        assert motor.mcp_konusur is False
        assert motor.butce_destegi is False

    def test_tur_kos_bitti_olayiyla_kapaniyor(self):
        """tur_kos her zaman 'bitti' olayıyla kapanıyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["test output\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                olay_listesi = list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))

                assert any(o.tur == "bitti" for o in olay_listesi)
                bitti_olay = [o for o in olay_listesi if o.tur == "bitti"][0]
                assert bitti_olay.ek["basarili"] is True
                # Doğrulanmış bayrakların komutta olması
                mock_popen.assert_called_once()
                komut = mock_popen.call_args[0][0]
                assert any("gemini" in str(arg) for arg in komut)
                assert "-p" in komut
                assert "test prompt" in komut  # -p'ye doğrudan metin geçilmeli
                assert "--output-format" in komut
                assert "json" in komut

    def test_basarili_komut_calistirmasi(self):
        """Başarılı çalıştırma"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["output data\n", '{"result": "ok"}\n'])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                olay_listesi = list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))
                bitti_olay = [o for o in olay_listesi if o.tur == "bitti"][0]

                assert bitti_olay.ek["basarili"] is True
                assert "output data" in bitti_olay.govde

    def test_basarisiz_komut_calistirmasi(self):
        """Başarısız çalıştırma"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 1
                mock_process.stdout = iter([])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = "error message"
                mock_popen.return_value = mock_process

                olay_listesi = list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))
                bitti_olay = [o for o in olay_listesi if o.tur == "bitti"][0]

                assert bitti_olay.tur == "bitti"
                assert bitti_olay.ek["basarili"] is False
                assert bitti_olay.ek["hata"] == "error message"

    def test_gemini_api_key_kontrol(self):
        """GEMINI_API_KEY ortam değişkeni kontrol edilir"""
        motor = GeminiMotoru()

        # API anahtarı olmadığında hata
        os.environ.pop("GEMINI_API_KEY", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(MotorHatasi) as exc_info:
                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))
            assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_p_bayragina_metin_dogru_ekleniyor(self):
        """Metin -p bayrağına doğrudan eklenmeli"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["sonuc\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                metin_test = "Bana yardim et"
                list(motor.tur_kos(
                    metin_test,
                    klasor=tmpdir
                ))

                # Komut kontrol
                komut = mock_popen.call_args[0][0]
                assert "-p" in komut
                idx = komut.index("-p")
                assert komut[idx + 1] == metin_test

    def test_gemini_api_key_sizmama(self):
        """GEMINI_API_KEY log/exception mesajlarında geçmemeli"""
        motor = GeminiMotoru()
        api_key = "super-secret-key-12345"
        os.environ["GEMINI_API_KEY"] = api_key

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["result\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                olay_listesi = list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))

                # Tüm olay içeriğini kontrol - API anahtarı OLMAMALI
                for olay in olay_listesi:
                    # govde alanında anahtar geçmemeli
                    assert api_key not in olay.govde
                    # ek alanındaki tüm değerlerde geçmemeli
                    for key, val in olay.ek.items():
                        if isinstance(val, str):
                            assert api_key not in val
                    # Olay string temsili de anahtar içermemeli
                    assert api_key not in str(olay)

    def test_gemini_api_key_hata_mesajında_geçmemeli(self):
        """API anahtarı MotorHatasi mesajlarında geçmemeli"""
        motor = GeminiMotoru()
        api_key = "secret-gemini-key"
        os.environ["GEMINI_API_KEY"] = api_key

        with tempfile.TemporaryDirectory() as tmpdir:
            # Hata durumunda da anahtar sızmaması
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                # Genel Exception simule et
                mock_popen.side_effect = Exception("Some error")

                olay_listesi = list(motor.tur_kos(
                    "test",
                    klasor=tmpdir
                ))
                bitti_olay = [o for o in olay_listesi if o.tur == "bitti"][0]

                # Hata mesajında API anahtarı OLMAMALI
                hata_msg = bitti_olay.ek.get("hata", "")
                assert api_key not in hata_msg
                assert "secret" not in hata_msg.lower()

    def test_butce_desteklenmiyorsa_hatasi(self):
        """Bütçe desteklenmiyorsa MotorHatasi atılır"""
        motor = GeminiMotoru()
        assert motor.butce_destegi is False

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(MotorHatasi) as exc_info:
                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir,
                    butce_usd=100
                ))

            assert "butce tavani uygulayamaz" in str(exc_info.value)

    def test_efor_desteklenmiyorsa_hatasi(self):
        """Efor parametresi desteklenmiyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(MotorHatasi) as exc_info:
                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir,
                    efor="yuksek"
                ))

            assert "efor" in str(exc_info.value).lower()

    def test_yazabilir_false_approval_mode_plan(self):
        """yazabilir=False --approval-mode plan ile uygulanıyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["result\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir,
                    yazabilir=False
                ))

                # Komut kontrol
                komut = mock_popen.call_args[0][0]
                assert "--approval-mode" in komut
                idx = komut.index("--approval-mode")
                assert komut[idx + 1] == "plan"

    def test_yazabilir_true_approval_mode_default(self):
        """yazabilir=True --approval-mode default ile uygulanıyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["result\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir,
                    yazabilir=True
                ))

                # Komut kontrol
                komut = mock_popen.call_args[0][0]
                assert "--approval-mode" in komut
                idx = komut.index("--approval-mode")
                assert komut[idx + 1] == "default"

    def test_zaman_asimi_desteklenmiyorsa_hatasi(self):
        """zaman_asimi parametresi desteklenmiyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(MotorHatasi) as exc_info:
                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir,
                    zaman_asimi=60
                ))

            assert "zaman_asimi" in str(exc_info.value).lower()

    def test_mcp_yapilandirma_desteklenmiyorsa_hatasi(self):
        """mcp_yapilandirma desteklenmiyor - MotorHatasi atılır"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(MotorHatasi) as exc_info:
                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir,
                    mcp_yapilandirma='{"mcpServers": {"fs": {}}}'
                ))

            assert "mcp_yapilandirma uygulayamaz" in str(exc_info.value)

    def test_oturum_id_komuta_ekleniyor(self):
        """oturum_id parametresi komuta ekleniyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = ("", "")
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test",
                    klasor=tmpdir,
                    oturum_id="abc123"
                ))

                komut = mock_popen.call_args[0][0]
                assert "--session-id" in komut
                idx = komut.index("--session-id")
                assert komut[idx + 1] == "abc123"

    def test_model_komuta_ekleniyor(self):
        """model parametresi komuta ekleniyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = ("", "")
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test",
                    klasor=tmpdir,
                    model="gemini-2.0"
                ))

                komut = mock_popen.call_args[0][0]
                assert "--model" in komut
                idx = komut.index("--model")
                assert komut[idx + 1] == "gemini-2.0"

    def test_ek_klasorler_komuta_ekleniyor(self):
        """ek_klasorler parametresi komuta ekleniyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = ("", "")
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test",
                    klasor=tmpdir,
                    ek_klasorler=("/path1", "/path2")
                ))

                komut = mock_popen.call_args[0][0]
                assert komut.count("--include-directories") == 2
                assert "/path1" in komut
                assert "/path2" in komut

    def test_izinli_araclar_komuta_ekleniyor(self):
        """izinli_araclar parametresi komuta ekleniyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = ("", "")
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test",
                    klasor=tmpdir,
                    izinli_araclar=("bash", "edit")
                ))

                komut = mock_popen.call_args[0][0]
                assert komut.count("--allowed-tools") == 2
                assert "bash" in komut
                assert "edit" in komut

    def test_musait_mi_gemini_var(self):
        """musait_mi() calistirilabilir yol varken True"""
        motor = GeminiMotoru(calistirilabilir="/usr/bin/gemini")
        assert motor.musait_mi() is True

    def test_musait_mi_gemini_yok(self):
        """musait_mi() calistirilabilir yol yokken False"""
        with patch("gemini.gemini.GeminiMotoru._calistirilabilir_bul") as mock_bul:
            mock_bul.return_value = ""
            motor = GeminiMotoru(calistirilabilir="")
            assert motor.musait_mi() is False

    def test_arguman_dogrula_satir_sonu_tasiyan_arguman_hatasi(self):
        """_arguman_dogrula() .cmd + newline argüman tuzağını farkeder"""
        with patch("gemini.gemini.GeminiMotoru._calistirilabilir_bul") as mock_bul:
            # .cmd fallback'ini simüle et
            mock_bul.return_value = "C:\\Users\\test\\AppData\\Roaming\\npm\\gemini.cmd"
            motor = GeminiMotoru(calistirilabilir="")

            # Satır sonu taşıyan metin komut tuzağını tetikler
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(MotorHatasi) as exc_info:
                    list(motor.tur_kos(
                        "test\nprompt",  # Satır sonu taşıyan metin
                        klasor=tmpdir
                    ))

                assert "satir sonu tasiyan arguman" in str(exc_info.value).lower()
                assert ".cmd" in str(exc_info.value).lower()

    def test_arguman_dogrula_gercek_executable_gecisi(self):
        """_arguman_dogrula() gerçek executable (.exe) ile satır sonu argümanı geçer"""
        motor = GeminiMotoru(calistirilabilir="C:\\path\\to\\gemini.exe")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["result\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                # Satır sonu taşıyan metin, gerçek .exe ise sorun yok
                list(motor.tur_kos(
                    "test\nprompt",
                    klasor=tmpdir
                ))

                # Popen çağrılmış demektir (hata atılmadı)
                mock_popen.assert_called_once()

    def test_skip_trust_bayragina_komuta_ekleniyor(self):
        """--skip-trust bayrağı her zaman komuta ekleniyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["result\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))

                komut = mock_popen.call_args[0][0]
                assert "--skip-trust" in komut

    def test_nabiz_olaylari_emit_ediliyor(self):
        """Stdout satır satır okunurken nabız olayları emit ediliyor"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = iter(["line1\n", "line2\n", "line3\n"])
                mock_process.stderr = MagicMock()
                mock_process.stderr.read.return_value = ""
                mock_popen.return_value = mock_process

                olay_listesi = list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))

                # 3 satır = 3 nabız + 1 bitti = 4 olay
                nabiz_olaylari = [o for o in olay_listesi if o.tur == "nabiz"]
                bitti_olaylari = [o for o in olay_listesi if o.tur == "bitti"]

                assert len(nabiz_olaylari) == 3
                assert len(bitti_olaylari) == 1
                # Bitti olay içeriği doğru
                assert bitti_olaylari[0].govde == "line1\nline2\nline3"

    def test_popen_hata_durumu(self):
        """subprocess.Popen hata verirse olay döndür"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gemini.gemini.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = FileNotFoundError("Command not found")

                olay_listesi = list(motor.tur_kos(
                    "test prompt",
                    klasor=tmpdir
                ))
                olay = olay_listesi[0]

                assert olay.tur == "bitti"
                assert olay.ek["basarili"] is False
                assert olay.ek["sebep"] == "motor_yok"

    def test_bos_brifing_hatasi(self):
        """Boş brifing hata atar"""
        motor = GeminiMotoru()

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(MotorHatasi) as exc_info:
                list(motor.tur_kos(
                    "",
                    klasor=tmpdir
                ))

            assert "bos brifing" in str(exc_info.value).lower()

    def test_gecersiz_klasor_hatasi(self):
        """Geçersiz klasör hata atar"""
        motor = GeminiMotoru()

        with pytest.raises(MotorHatasi) as exc_info:
            list(motor.tur_kos(
                "test",
                klasor="/nonexistent/path/12345"
            ))

            assert "klasor" in str(exc_info.value).lower()
