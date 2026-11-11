"""T25 Carga inicial, pela linha de comando (rodar dentro do container da API).

Prévia (não grava nada; gera o relatório):
    python -m app.carga --pasta /carga/planilhas --saida /carga/relatorios
Importar (limpa os dados operacionais e recarrega):
    python -m app.carga --pasta /carga/planilhas --saida /carga/relatorios --importar --limpar

Em produção (APP_ENV=prod) a limpeza exige também --confirmo-producao.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_config
from app.core.db import SessionLocal
from app.integrations.mega import fabrica
from app.models import Liga, MegaSaldo, Usuario

from . import gravar, planilhas, plano, relatorio

log = logging.getLogger("estoqueack.carga")


def _verificador_op():
    cache: dict[int, bool | None] = {}
    try:
        g = fabrica.obter()
    except Exception as e:  # noqa: BLE001
        log.warning("Mega indisponível, OPs não serão conferidas: %s", e)
        g = None

    def existe(op: int) -> bool | None:
        if g is None:
            return None
        if op not in cache:
            try:
                cache[op] = g.ordem_producao(op) is not None
            except Exception:  # noqa: BLE001
                cache[op] = None
        return cache[op]
    return existe


def contexto(db, conferir_ops: bool, correcoes: dict | None = None) -> plano.Contexto:
    # ligas criadas por uma carga anterior continuam aparecendo como "liga nova" na lista de pendências
    ligas = {l.codigo: float(l.densidade) for l in db.scalars(select(Liga)) if not l.nome.endswith("(criada na carga)")}
    mega = {m.codigo: {"saldo_kg": m.saldo_kg, "descricao": m.descricao, "peso_especifico": m.peso_especifico}
            for m in db.scalars(select(MegaSaldo))}
    quando = db.scalar(select(func.max(MegaSaldo.atualizado_em)))
    return plano.Contexto(ligas, mega, quando.strftime("%Y-%m-%d %H:%M") if quando else None,
                          _verificador_op() if conferir_ops else (lambda _op: None), date.today(), _kardex(),
                          correcoes or {})


def _kardex():
    """§10.7 item 4: códigos com movimento no kardex do Mega nos últimos 2 anos (730 dias)."""
    def consultar(codigos: list[int]) -> set[int] | None:
        try:
            return fabrica.obter().codigos_com_movimento(codigos, date.today() - timedelta(days=730))
        except Exception as e:  # noqa: BLE001
            log.error("kardex do Mega indisponível: %s", e)
            return None
    return consultar


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="python -m app.carga", description="Carga inicial das planilhas (T25)")
    ap.add_argument("--pasta", required=True, type=Path, help="Pasta com as 4 planilhas")
    ap.add_argument("--saida", required=True, type=Path, help="Pasta para o relatório")
    ap.add_argument("--importar", action="store_true", help="Grava (sem isso, só a prévia)")
    ap.add_argument("--limpar", action="store_true", help="Apaga os dados operacionais antes de gravar")
    ap.add_argument("--confirmo-producao", action="store_true")
    ap.add_argument("--sem-conferir-ops", action="store_true", help="Não consulta as OPs no Mega")
    ap.add_argument("--correcoes", type=Path, help="JSON com as correções respondidas (fora do repositório)")
    ap.add_argument("--usuario", default="eduardo.macedo", help="Login gravado como autor da carga")
    a = ap.parse_args(argv)
    cfg = get_config()
    t0 = time.time()
    try:
        est, hist = planilhas.ler_estoque_2026(a.pasta)
        geral = planilhas.ler_geral(a.pasta)
        corte = planilhas.ler_corte(a.pasta)
        sas = planilhas.ler_sa(a.pasta)
    except planilhas.EstruturaMudou as e:
        log.error("PAROU: a estrutura de uma planilha mudou: %s", e)
        return 2
    log.info("planilhas lidas em %.1f s", time.time() - t0)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    correcoes = {}
    if a.correcoes:
        import json
        try:
            correcoes = json.loads(a.correcoes.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.error("PAROU: arquivo de correções ilegível (%s): %s", a.correcoes, e)
            return 2
    with SessionLocal() as db:
        pl = plano.montar(contexto(db, not a.sem_conferir_ops, correcoes), est, hist, geral, corte, sas)
        log.info("plano: %s", pl.contagens)
        if not a.importar:
            p = relatorio.gerar(pl, a.saida / f"carga_previa_{carimbo}.xlsx", titulo=f"PRÉVIA {carimbo} (nada gravado)")
            log.info("prévia: %s", p)
            return 0
        if not gravar.base_vazia(db) and not a.limpar:
            log.error("A base já tem lotes/solicitações. Use --limpar para recarregar.")
            return 3
        if a.limpar and cfg.app_env == "prod" and not a.confirmo_producao:
            log.error("Em produção, a limpeza exige --confirmo-producao.")
            return 4
        u = db.scalar(select(Usuario).where(Usuario.login == a.usuario))
        try:
            if a.limpar:
                gravar.limpar(db)
            resumo = gravar.gravar(db, pl, usuario_id=u.id if u else None,
                                   arquivos={n: str(a.pasta / n) for n in planilhas.arquivos(a.pasta)})
            db.flush()
            conf = gravar.conferencia_banco(db)
            db.commit()
        except gravar.CargaRecusada as e:
            db.rollback()
            log.error("Carga recusada: %s", e)
            return 5
        p = relatorio.gerar(pl, a.saida / f"carga_resultado_{carimbo}.xlsx", titulo=f"CARGA GRAVADA {carimbo}",
                            conferencia_banco=conf, resumo_gravado=resumo)
        log.info("gravado: %s · relatório: %s · %.1f s", resumo, p, time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
