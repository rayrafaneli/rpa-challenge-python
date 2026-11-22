import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import robo  # noqa: E402

CAB = ["First Name", "Last Name ", "Company Name", "Role in Company", "Address", "Email", "Phone Number"]


def planilha(tmp_path, linhas, cab=CAB):
    wb = Workbook()
    ws = wb.active
    ws.append(cab)
    for linha in linhas:
        ws.append(linha)
    caminho = tmp_path / "challenge.xlsx"
    wb.save(caminho)
    return caminho


def test_normaliza_cabecalho_e_valores(tmp_path):
    p = planilha(tmp_path, [["John ", "Smith", "IT Solutions", "Analyst", "98 North Road", "jsmith@itsolutions.co.uk", 40716543298]])
    regs = robo.ler_registros(p)
    assert regs == [{
        "First Name": "John", "Last Name": "Smith", "Company Name": "IT Solutions", "Role in Company": "Analyst",
        "Address": "98 North Road", "Email": "jsmith@itsolutions.co.uk", "Phone Number": "40716543298",
    }]


def test_ignora_linhas_vazias(tmp_path):
    p = planilha(tmp_path, [["A", "B", "C", "D", "E", "F", "1"], [None] * 7, ["G", "H", "I", "J", "K", "L", "2"]])
    assert [r["First Name"] for r in robo.ler_registros(p)] == ["A", "G"]


def test_falha_se_faltar_coluna(tmp_path):
    p = planilha(tmp_path, [["A", "B"]], cab=["First Name", "Last Name"])
    with pytest.raises(ValueError, match="colunas ausentes"):
        robo.ler_registros(p)


def test_todo_campo_do_mapa_e_unico():
    assert len(set(robo.MAPA.values())) == len(robo.MAPA) == 7
