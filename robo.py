"""
RPA Challenge (rpachallenge.com) resolvido com Python + Playwright.

O desafio: preencher 10 vezes um formulário de 7 campos a partir de uma planilha Excel.
A cada envio os campos trocam de lugar e os ids mudam, então o robô nunca usa posição nem id:
cada coluna da planilha vai para o campo pelo nome lógico dele (atributo ng-reflect-name).

Uso:
    python robo.py              # headless, grava o resultado em saida/
    python robo.py --visivel    # abre o navegador na tela
    python robo.py --demo       # salva um quadro por campo em saida/quadros (usado no GIF do README)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import Page, sync_playwright

URL = "https://rpachallenge.com/"
SAIDA = Path(__file__).resolve().parent / "saida"

# coluna da planilha -> nome lógico do campo no formulário
MAPA = {
    "First Name": "labelFirstName",
    "Last Name": "labelLastName",
    "Company Name": "labelCompanyName",
    "Role in Company": "labelRole",
    "Address": "labelAddress",
    "Email": "labelEmail",
    "Phone Number": "labelPhone",
}

log = logging.getLogger("robo")


def baixar_planilha(page: Page, destino: Path) -> Path:
    """Baixa a planilha pelo próprio link da página, como um usuário faria."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with page.expect_download() as dl:
        page.get_by_text("Download Excel").click()
    dl.value.save_as(destino)
    log.info("planilha baixada: %s", destino.name)
    return destino


def ler_registros(planilha: Path) -> list[dict[str, str]]:
    """Lê a planilha e devolve um dict por linha, com cabeçalhos sem espaços sobrando."""
    ws = load_workbook(planilha, read_only=True).active
    linhas = ws.iter_rows(values_only=True)
    cabecalho = [str(c).strip() if c is not None else "" for c in next(linhas)]
    faltando = set(MAPA) - set(cabecalho)
    if faltando:
        raise ValueError(f"colunas ausentes na planilha: {sorted(faltando)}")
    registros = []
    for linha in linhas:
        if not any(v not in (None, "") for v in linha):
            continue
        registros.append({c: "" if v is None else str(v).strip() for c, v in zip(cabecalho, linha) if c})
    return registros


def preencher(page: Page, registro: dict[str, str], foto=None) -> None:
    for coluna, nome in MAPA.items():
        page.locator(f'input[ng-reflect-name="{nome}"]').fill(registro[coluna])
        if foto:
            foto()
    page.locator('input[type="submit"]').click()


class Quadros:
    """No modo demo, guarda um quadro (JPEG) a cada campo preenchido para montar o GIF."""

    def __init__(self, page: Page, pasta: Path):
        self.page, self.pasta, self.n = page, pasta, 0
        pasta.mkdir(parents=True, exist_ok=True)
        for f in pasta.glob("*.jpg"):
            f.unlink()

    def __call__(self) -> None:
        self.n += 1
        self.page.screenshot(path=str(self.pasta / f"{self.n:04d}.jpg"), type="jpeg", quality=85)


def resultado(page: Page) -> dict:
    texto = page.locator(".message2").inner_text(timeout=10_000)
    taxa = re.search(r"(\d+)%", texto)
    campos = re.search(r"(\d+) out of (\d+)", texto)
    ms = re.search(r"(\d+) milliseconds", texto)
    return {
        "mensagem": " ".join(texto.split()),
        "taxa_sucesso_pct": int(taxa.group(1)) if taxa else None,
        "campos_certos": int(campos.group(1)) if campos else None,
        "campos_total": int(campos.group(2)) if campos else None,
        "tempo_site_ms": int(ms.group(1)) if ms else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--visivel", action="store_true", help="abre o navegador na tela")
    ap.add_argument("--demo", action="store_true", help="salva um quadro por campo em saida/quadros (para o GIF)")
    ap.add_argument("--canal", default=None, help="canal do navegador (ex.: msedge, chrome)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.canal, headless=not args.visivel)
        ctx = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 760})
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        registros = ler_registros(baixar_planilha(page, SAIDA / "challenge.xlsx"))
        log.info("%d registros para enviar", len(registros))

        foto = Quadros(page, SAIDA / "quadros") if args.demo else None
        if foto:
            foto()
        inicio = time.perf_counter()
        page.get_by_role("button", name="Start").click()
        for i, reg in enumerate(registros, 1):
            preencher(page, reg, foto)
            log.info("rodada %02d/%d enviada (%s %s)", i, len(registros), reg["First Name"], reg["Last Name"])
        res = resultado(page)
        res["tempo_robo_s"] = round(time.perf_counter() - inicio, 2)
        if foto:
            page.wait_for_timeout(800)
            foto()
        page.screenshot(path=str(SAIDA / "resultado.png"))
        ctx.close()
        browser.close()

    res["executado_em"] = datetime.now().isoformat(timespec="seconds")
    (SAIDA / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("resultado: %s", res["mensagem"])


if __name__ == "__main__":
    main()
