"""Parte C1: matriz perfil × tela (especificação §4.1, R009) aplicada pela API.

Para cada ação, os perfis que NÃO têm permissão recebem 403; os que têm passam da checagem de perfil (podem receber
404/409/422 porque o corpo é vazio e os ids não existem — o que importa aqui é não ser 403). Admin pode tudo.
"""
import pytest

from tests.fluxo_util import criar_usuarios, entrar

pytest.importorskip("fastapi")

ITU, RJ, ANALISE, ADMIN = "itu", "rj", "analise", "admin"

# (método, url, perfis com permissão, tela)
MATRIZ = [
    ("POST", "/api/solicitacoes/validar", {ITU}, "T07 nova solicitação"),
    ("POST", "/api/solicitacoes/999/cancelar", {ITU}, "T08 cancelar"),
    ("POST", "/api/solicitacoes/999/trocar-op", {ITU}, "T08 trocar OP"),
    ("GET", "/api/fila-rj", {ITU, RJ}, "T09 fila RJ (Itu só consulta)"),
    ("POST", "/api/solicitacoes/999/material-insuficiente", {RJ}, "T09 material insuficiente"),
    ("POST", "/api/solicitacoes/999/corte/validar", {RJ}, "T10 registrar corte"),
    ("GET", "/api/cops", {ITU, RJ, ANALISE}, "T11 COP (consulta)"),
    ("POST", "/api/cops", {RJ}, "T11 novo COP"),
    ("POST", "/api/cops/999/fechar", {RJ}, "T11 fechar COP"),
    ("POST", "/api/cops/999/nf", {RJ}, "T11 NF"),
    ("GET", "/api/recebimentos", {ITU, RJ}, "T12 receber (RJ consulta)"),
    ("POST", "/api/cops/999/receber/validar", {ITU}, "T12 receber"),
    ("POST", "/api/cortes-itu/validar", {ITU}, "T13 corte em Itu"),
    ("GET", "/api/sas", {ITU, RJ, ANALISE}, "T14 SA (consulta)"),
    ("POST", "/api/sas/999/codigo/validar", {ITU}, "T14 informar código"),
    ("PATCH", "/api/sas/999", {ITU, ANALISE}, "T14 editar (Análise: R$/kg)"),
    ("POST", "/api/entradas-nf/validar", {RJ}, "T06 entrada por NF"),
    ("POST", "/api/lotes/999/destinacoes", {ITU, ANALISE}, "T17 reservas e restrições"),
    ("POST", "/api/lotes/999/ajuste/validar", {ITU}, "T18 ajuste"),
    ("POST", "/api/movimentos/999/estorno", {ITU, RJ}, "T18 estorno (RJ só os próprios)"),
    ("POST", "/api/lotes/999/atribuir-origem", {ITU}, "T05 atribuir origem"),
    ("PATCH", "/api/parametros/TOLERANCIA_EXCESSO_PCT", set(), "T23 parâmetros (só Admin)"),
    ("POST", "/api/mega/sincronizar", {ITU, ANALISE}, "Sincronizar agora"),
]


@pytest.fixture()
def usuarios(client):
    return criar_usuarios(client)


@pytest.mark.parametrize("perfil", [ITU, RJ, ANALISE, ADMIN])
def test_matriz_perfil_tela(client, usuarios, perfil):
    h = entrar(client, usuarios[perfil])
    if perfil == ADMIN:
        # o admin de teste trocou a senha em criar_usuarios; entrar já devolve o CSRF
        pass
    erros = []
    for metodo, url, permitidos, tela in MATRIZ:
        r = client.request(metodo, url, json={}, headers=h)
        pode = perfil == ADMIN or perfil in permitidos
        if pode and r.status_code == 403:
            erros.append(f"{tela}: {perfil} deveria poder ({metodo} {url}) e recebeu 403")
        if not pode and r.status_code != 403:
            erros.append(f"{tela}: {perfil} NÃO deveria poder ({metodo} {url}) e recebeu {r.status_code}")
    assert not erros, "\n".join(erros)


def test_operacao_rj_nao_ve_rascunho_nem_lote_de_itu(client, usuarios):
    """P10: o Marcelo só enxerga RJ no Rio (lotes de outros estoques respondem 404)."""
    from tests.fluxo_util import catalogo_e_lotes
    ids = catalogo_e_lotes()
    h = entrar(client, usuarios[RJ])
    assert client.get(f"/api/lotes/{ids['lmega']}").status_code == 404
    assert client.get(f"/api/lotes/{ids['l33']}").status_code == 200
    estoques = {x["estoque"] for x in client.get("/api/lotes").json()["itens"]}
    assert estoques <= {"RJ_NO_RIO"}
    del h
