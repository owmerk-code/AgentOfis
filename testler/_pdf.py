# -*- coding: utf-8 -*-
"""Sinamalar icin elle kurulmus gecerli PDF (bagimlilik yok)."""

def pdf_yap(sayfalar: list) -> bytes:
    """Elle kurulmus gecerli PDF (Helvetica, her sayfa bir metin satiri)."""
    nesneler = []
    n = len(sayfalar)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    nesneler.append("<< /Type /Catalog /Pages 2 0 R >>")
    nesneler.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>")
    for i, metin in enumerate(sayfalar):
        akis = f"BT /F1 12 Tf 72 720 Td ({metin}) Tj ET"
        nesneler.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                        f"/Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 {3 + 2 * n} 0 R >> >> >>")
        nesneler.append(f"<< /Length {len(akis)} >>\nstream\n{akis}\nendstream")
    nesneler.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    govde = "%PDF-1.4\n"
    yerler = []
    for i, o in enumerate(nesneler, 1):
        yerler.append(len(govde.encode("latin-1")))
        govde += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(govde.encode("latin-1"))
    govde += f"xref\n0 {len(nesneler) + 1}\n0000000000 65535 f \n"
    govde += "".join(f"{y:010d} 00000 n \n" for y in yerler)
    govde += f"trailer\n<< /Size {len(nesneler) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return govde.encode("latin-1")
