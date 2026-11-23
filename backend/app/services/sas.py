"""T14 SA: fila, sugestão do código pelo item da peça acabada, código informado, confirmação no Mega e
exportações. As linhas nascem do COP fechado (caminhos A e B) e do corte em Itu de lote fiscal RJ (B2)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.formato import kg_br, pct_br
from app.domain.validacao import Nivel, Resultado
from app.integrations.mega import fabrica
from app.models import CadastroSa, CopItem, Lote, NfTransferencia, SolicitacaoCorte, Usuario

from . import auditoria
from .base import FINANCEIRO, ErroNegocio, NaoEncontrado, Previa, agora, exigir_sem_pendencias, notificar, parametro
from .estoque import bitola
from .fluxo import recalcular_solicitacao

log = logging.getLogger(__name__)

# Emitente da NF de transferência RJ → Itu. Lançamento novo: só Fio Certo (Eduardo, 2026-11-17). MEDIO_VALE e OUTRO
# continuam válidos só na leitura (NFs já gravadas); a carga grava EMITENTE_CARGA (app/carga/gravar.py).
EMITENTES_NOVOS = ("FIO_CERTO",)
EMITENTES_HISTORICO = ("FIO_CERTO", "MEDIO_VALE", "OUTRO")


@dataclass
class Sugestao:
    codigo: int | None
    descricao: str | None
    ncm: str | None
    icms: str | None
    ipi: str | None
    outros: list[int]


def sa_da_estrutura(op: int | None) -> tuple[int, str | None] | None:
    """SA que o Mega já colocou na estrutura da OP (PRO_DEMANDA_DEP), quando a OP é de material RJ.
    Mega fora do ar → None (fica só o histórico)."""
    if not op:
        return None
    try:
        comps = fabrica.obter().estrutura_op(op)
    except Exception:  # noqa: BLE001 - sem o Mega fica só o histórico, mas o motivo vai para o log
        log.warning("Estrutura da OP %s não lida no Mega; SA sugerido só pelo histórico", op, exc_info=True)
        return None
    sa = next((c for c in comps if c.tipo == "SA"), None)
    return (sa.codigo, sa.descricao) if sa else None


def sugerir(db: Session, item_codigo: int | None, *, exceto_id: int | None = None, op: int | None = None) -> Sugestao:
    """Código de SA sugerido: 1º o SA da estrutura da OP no Mega (mapeado em 2026-11-03); senão, o mais recente já
    usado para o item da peça acabada (regra do Matheus, 2026-10-30)."""
    est = sa_da_estrutura(op)
    if not item_codigo and not est:
        return Sugestao(None, None, None, None, None, [])
    if not item_codigo:
        return Sugestao(est[0], est[1], None, None, None, [])
    q = (select(CadastroSa).where(CadastroSa.item_codigo == item_codigo, CadastroSa.sa_codigo.is_not(None),
                                  CadastroSa.situacao == "CONFIRMADO")
         .order_by(CadastroSa.data.desc(), CadastroSa.id.desc()))
    if exceto_id:
        q = q.where(CadastroSa.id != exceto_id)
    hist = list(db.scalars(q.limit(200)))
    if not hist and not est:
        return Sugestao(None, None, None, None, None, [])
    if est:
        # fiscais (ICMS/IPI/NCM) do último SA com o mesmo código; se não houver, do último do item
        h = next((x for x in hist if x.sa_codigo == est[0]), hist[0] if hist else None)
        codigo, descricao = est[0], est[1] or (h.sa_descricao if h else None)
    else:
        h = hist[0]
        codigo, descricao = h.sa_codigo, h.sa_descricao
    outros = []
    for x in hist:
        if x.sa_codigo != codigo and x.sa_codigo not in outros:
            outros.append(x.sa_codigo)
    return Sugestao(codigo, descricao, h.ncm if h else None, h.icms if h else None, h.ipi if h else None, outros)


def _dimensao(lote: Lote) -> str:
    return "RETO" if lote.item.formato == "RETO" else bitola(lote.item)


def criar_linha(db: Session, *, origem: str, lote: Lote, op: int, item_codigo: int | None, item_descricao: str | None,
                cliente: str | None, pedido: str | None, quantidade: int | None, peso_kg: float,
                solicitacao_id: int | None = None, cop_item_id: int | None = None,
                corte_itu_id: int | None = None) -> CadastroSa:
    sug = sugerir(db, item_codigo, op=op)
    raiz_ct = lote.conteiner.codigo if lote.conteiner else None
    sa = CadastroSa(origem=origem, cop_item_id=cop_item_id, corte_itu_id=corte_itu_id, solicitacao_id=solicitacao_id,
                    lote_id=lote.id, data=agora().date(), op=op, item_codigo=item_codigo,
                    item_descricao=item_descricao, cliente=cliente, pedido=pedido, material=lote.item.liga.codigo,
                    dimensao=_dimensao(lote), conteiner=raiz_ct, quantidade=quantidade, peso_kg=round(peso_kg, 3),
                    sa_codigo=sug.codigo, sa_codigo_sugerido=sug.codigo, sa_novo=sug.codigo is None,
                    sa_descricao=sug.descricao or (f"SA {item_descricao} - CÓD.{item_codigo}"
                                                   if item_descricao and item_codigo else None),
                    ncm=sug.ncm, icms=sug.icms, ipi=sug.ipi, situacao="PENDENTE")
    db.add(sa)
    db.flush()
    return sa


def obter(db: Session, sa_id: int, *, travar: bool = False, usuario: Usuario | None = None) -> CadastroSa:
    q = select(CadastroSa).where(CadastroSa.id == sa_id)
    if travar:
        q = q.with_for_update().execution_options(populate_existing=True)
    sa = db.scalar(q)
    if sa is None or not visivel(sa, usuario):
        raise NaoEncontrado("SA não encontrado.")
    return sa


def _marcar_alteracao(db: Session, sa: CadastroSa) -> None:
    if sa.exportado_renato_em and not sa.alterado_apos_exportar:
        sa.alterado_apos_exportar = True
        notificar(db, perfis=("ANALISE",), tipo="SA_ALTERADO_APOS_EXPORTAR",
                  texto=f"SA da OP {sa.op} foi alterado depois de exportado.", link=f"/sa?id={sa.id}")


CAMPOS_EDITAVEIS = ("rs_kg", "sa_descricao", "ncm", "icms", "ipi", "pedido", "quantidade", "peso_kg")


def editar(db: Session, sa_id: int, dados: dict[str, Any], *, usuario: Usuario, ip: str | None) -> CadastroSa:
    sa = obter(db, sa_id, travar=True)
    if sa.situacao == "CONFIRMADO" and set(dados) - {"rs_kg"}:
        raise ErroNegocio("SA confirmado no Mega: só o R$/kg pode ser alterado.")
    if "rs_kg" in dados and not dados["rs_kg"] and sa.origem != "CARGA":
        # spec v3.16 T14 [proposta, P44(d)]: depois da NF, o R$/kg pode ser corrigido, mas não apagado
        if sa.nf_id is not None:
            raise ErroNegocio("A NF de transferência já foi informada: o R$/kg pode ser corrigido, mas não apagado.")
        # spec v3.19 T14 (Eduardo, 2026-11-19): o SA só fecha com o precificador, então o fechado não fica sem ele
        if sa.situacao == "CONFIRMADO":
            raise ErroNegocio("SA fechado: o R$/kg do precificador pode ser corrigido, mas não apagado.")
    pronto_antes = sa.cop_item_id is not None and _cop_pronto(db, db.get(CopItem, sa.cop_item_id).cop)
    antes = {c: getattr(sa, c) for c in dados}
    for c, v in dados.items():
        if c in CAMPOS_EDITAVEIS:
            setattr(sa, c, v)
    _marcar_alteracao(db, sa)
    # o SA que já estava no Mega esperando o precificador fecha aqui (o aviso ao RJ sai dentro de _fechar)
    if not _fechar(db, sa):
        _avisar_se_cop_pronto(db, sa, antes=pronto_antes)
    auditoria.registrar(db, "SA_EDITADO", usuario_id=usuario.id, entidade="sa", entidade_id=sa.id, antes=antes,
                        depois=dados, ip=ip)
    db.commit()
    return sa


def preparar(db: Session, ids: list[int], *, usuario: Usuario, ip: str | None) -> list[CadastroSa]:
    sas = [obter(db, i, travar=True) for i in ids]
    for sa in sas:
        if sa.situacao == "PENDENTE":
            sa.situacao, sa.preparado_em = "PREPARADO", agora()
    auditoria.registrar(db, "SA_PREPARADO", usuario_id=usuario.id, entidade="sa", entidade_id=",".join(map(str, ids)),
                        ip=ip)
    db.commit()
    return sas


def validar_codigo(db: Session, sa: CadastroSa, codigo: int) -> Previa:
    p = Previa()
    if sa.situacao == "CONFIRMADO":
        p.resultado.adicionar("SA_JA_CONFIRMADO", Nivel.ERRO, "Este SA já foi confirmado no Mega.")
    if sa.sa_codigo_sugerido and codigo != sa.sa_codigo_sugerido:
        p.resultado.adicionar("SA_CODIGO_TROCADO", Nivel.CIENCIA,
                              f"O item {sa.item_codigo} já usou o SA {sa.sa_codigo_sugerido}. Justifique a troca "
                              f"para {codigo}.", sugerido=sa.sa_codigo_sugerido, informado=codigo)
    st = _ler_sa_mega(db, codigo, sa)
    if st is not None and not st.existe:
        p.resultado.adicionar("SA_NAO_ENCONTRADO_MEGA", Nivel.ALERTA,
                              f"O código {codigo} não existe no Mega. Confira a digitação.", sa_codigo=codigo)
    elif st is not None and st.ativo is False:
        p.resultado.adicionar("SA_INATIVO_MEGA", Nivel.CIENCIA,
                              f"O SA {codigo} está INATIVO no Mega ({st.descricao}). Justifique o uso.",
                              sa_codigo=codigo)
    if st is not None and st.existe and ipi_difere(sa.ipi, st.ipi_pct):
        p.resultado.adicionar("IPI_DIFERENTE_MEGA", Nivel.ALERTA,
                              f"IPI do histórico do item ({sa.ipi}) diferente do IPI do NCM {st.ncm} no Mega "
                              f"({pct_br(st.ipi_pct)}). Confira antes de cadastrar.", ipi=sa.ipi, ipi_mega=st.ipi_pct)
    p.frase = f"SA {codigo} para a OP {sa.op} ({kg_br(sa.peso_kg or 0)}). O sistema confirma lendo o Mega."
    return p


def _numero_nf(n) -> str:
    return str(n or "").strip().lstrip("0")


def ipi_difere(ipi_historico: str | None, ipi_mega_pct: float | None) -> bool:
    """IPI do histórico (planilha: fração 0,052; às vezes % 5,2) × alíquota do NCM no Mega (em %)."""
    if ipi_mega_pct is None or ipi_historico in (None, ""):
        return False
    try:
        v = float(str(ipi_historico).replace(",", ".").replace("%", "").strip())
    except ValueError:
        return False
    fracao = v / 100 if v > 1 else v
    return abs(fracao - ipi_mega_pct / 100) > 0.0005


def avisos(sa: CadastroSa) -> list[dict[str, Any]]:
    """Avisos cinza da T14 (R026, especificação v3.1): NF e IPI diferentes do que o Mega registrou."""
    mega = (sa.dados_extra or {}).get("mega") or {}
    out: list[dict[str, Any]] = []
    nf_mega = mega.get("nf_entrada")
    if nf_mega and sa.nf is not None and _numero_nf(sa.nf.numero) != _numero_nf(nf_mega):
        out.append({"codigo": "NF_DIFERENTE_MEGA", "nivel": "ALERTA", "nf": sa.nf.numero, "nf_mega": nf_mega,
                    "mensagem": f"A NF informada ({sa.nf.numero}) é diferente da NF da entrada do SA no Mega "
                                f"({nf_mega}). Confira."})
    if ipi_difere(sa.ipi, mega.get("ipi_pct")):
        out.append({"codigo": "IPI_DIFERENTE_MEGA", "nivel": "ALERTA", "ipi": sa.ipi, "ipi_mega": mega["ipi_pct"],
                    "mensagem": f"IPI do histórico do item ({sa.ipi}) diferente do IPI do NCM no Mega "
                                f"({pct_br(mega['ipi_pct'])})."})
    return out


def _janela(db: Session) -> int:
    """P24 (10/11): entradas no Mega a partir de SA_JANELA_ANTES_DIAS (T23, padrão 7) antes da data do SA."""
    return int(parametro(db, "SA_JANELA_ANTES_DIAS"))


def _ler_sa_mega(db: Session, codigo: int, sa: CadastroSa):
    """Leitura do SA no Mega para a prévia. Mega fora do ar não bloqueia (devolve None)."""
    try:
        return fabrica.obter().situacao_sa(codigo, sa.data - timedelta(days=_janela(db)))
    except Exception:  # noqa: BLE001
        return None


def informar_codigo(db: Session, sa_id: int, codigo: int, confirmacoes: dict[str, str], *, usuario: Usuario,
                    ip: str | None) -> CadastroSa:
    sa = obter(db, sa_id, travar=True)
    conf = exigir_sem_pendencias(validar_codigo(db, sa, codigo), confirmacoes)
    antes = sa.sa_codigo
    sa.sa_codigo, sa.situacao, sa.informado_em = codigo, "AGUARDANDO_MEGA", agora()
    # código novo ou corrigido: o que o Mega disse do código anterior não vale mais
    sa.dados_extra = {k: v for k, v in (sa.dados_extra or {}).items() if k != "mega"} or None
    sa.confirmacoes = {**(sa.confirmacoes or {}), **conf} or None
    _marcar_alteracao(db, sa)
    auditoria.registrar(db, "SA_CODIGO_INFORMADO", usuario_id=usuario.id, entidade="sa", entidade_id=sa.id,
                        antes={"sa_codigo": antes}, depois={"sa_codigo": codigo, "confirmacoes": conf}, ip=ip)
    db.flush()
    verificar(db, [sa])
    db.commit()
    return sa


def verificar(db: Session, sas: list[CadastroSa]) -> dict[str, Any]:
    """'Verificar no Mega agora': o código existe, está ativo e recebeu a carga (entrada por compra na filial 13 ou
    entrada na filial 3, em peças) a partir da data do SA − SA_JANELA_ANTES_DIAS (7). Ver consultas.SITUACAO_SA.
    Achado no Mega, o SA só fecha com o R$/kg do precificador (spec v3.19): sem ele, fica em Aguardando Mega com
    `sa_no_mega` e fecha quando o R$/kg for gravado (`editar`), sem ler o Mega de novo."""
    janela = _janela(db)
    try:
        g = fabrica.obter()
    except fabrica.MegaIndisponivel as e:
        return {"verificados": 0, "confirmados": 0, "falta_precificador": 0, "erro": str(e)}
    confirmados = falta_rs = 0
    for sa in sas:
        if sa.situacao != "AGUARDANDO_MEGA" or not sa.sa_codigo:
            continue
        if not sa_no_mega(sa):
            try:
                st = g.situacao_sa(sa.sa_codigo, sa.data - timedelta(days=janela))
            except Exception as e:  # noqa: BLE001
                return {"verificados": 0, "confirmados": confirmados, "falta_precificador": falta_rs,
                        "erro": f"Erro no Mega ({type(e).__name__})"}
            sa.verificado_mega_em = agora()
            if not (st is not None and st.existe and st.ativo is not False and st.qtd_entrada > 0):
                continue
            if st.descricao and not sa.sa_descricao:
                sa.sa_descricao = st.descricao
            if st.ncm and not sa.ncm:
                sa.ncm = st.ncm
            if st.ipi_pct is not None and not sa.ipi:
                sa.ipi = f"{st.ipi_pct / 100:.4g}"
            sa.dados_extra = {**(sa.dados_extra or {}),
                              "mega": {"qtd_entrada": st.qtd_entrada, "nf_entrada": st.nf_entrada,
                                       "ncm": st.ncm, "ipi_pct": st.ipi_pct}}
        if _fechar(db, sa):
            confirmados += 1
        else:
            falta_rs += 1
    db.flush()
    return {"verificados": len(sas), "confirmados": confirmados, "falta_precificador": falta_rs, "erro": None}


def sa_no_mega(sa: CadastroSa) -> bool:
    """O Mega já tem a carga do SA (gravado na verificação); se a linha não fechou, falta só o precificador."""
    return bool((sa.dados_extra or {}).get("mega"))


def precisa_precificador(sa: CadastroSa) -> bool:
    """SA da carga (histórico) fica como veio; os outros só fecham com o R$/kg do precificador."""
    return sa.origem != "CARGA"


def _fechar(db: Session, sa: CadastroSa) -> bool:
    """Eduardo, 2026-11-19 (spec v3.19 T14): o SA só fecha (CONFIRMADO) com o SA no Mega **e** o R$/kg do
    precificador. Devolve True se fechou agora."""
    if sa.situacao != "AGUARDANDO_MEGA" or not sa_no_mega(sa):
        return False
    if precisa_precificador(sa) and not tem_precificador(sa):
        return False
    sa.situacao, sa.confirmado_em = "CONFIRMADO", agora()
    _ao_confirmar(db, sa)
    return True


def confirmar_teste(db: Session, sa_id: int, sa_codigo: int | None, *, usuario: Usuario,
                    ip: str | None) -> CadastroSa:
    """Ferramenta de teste (contrato §7.1, só fora de produção; quem chama confere o modo de teste): marca o SA como
    CONFIRMADO sem ler o Mega, para o teste manual dos caminhos A e B, e segue igual à confirmação real: faz de conta
    que o Mega achou o SA; sem o R$/kg do precificador a linha fica esperando por ele (spec v3.19)."""
    sa = obter(db, sa_id, travar=True)
    if sa.situacao == "CONFIRMADO":
        raise ErroNegocio("Este SA já está confirmado.")
    codigo = sa_codigo or sa.sa_codigo
    if not codigo:
        raise ErroNegocio("Informe o código do SA para confirmar em teste.")
    antes = {"situacao": sa.situacao, "sa_codigo": sa.sa_codigo}
    em = agora()
    sa.sa_codigo, sa.situacao = codigo, "AGUARDANDO_MEGA"
    sa.informado_em = sa.informado_em or em
    sa.dados_extra = {**(sa.dados_extra or {}), "mega": {"teste": True},
                      "confirmacao_teste": {"usuario": usuario.login, "em": em.isoformat()}}
    _marcar_alteracao(db, sa)
    db.flush()
    _fechar(db, sa)
    auditoria.registrar(db, "SA_CONFIRMADO_TESTE", usuario_id=usuario.id, entidade="sa", entidade_id=sa.id,
                        antes=antes, depois={"situacao": sa.situacao, "sa_codigo": codigo,
                                             "confirmacao": "confirmação de teste", "usuario": usuario.login},
                        ip=ip)
    db.commit()
    return sa


def _ao_confirmar(db: Session, sa: CadastroSa) -> None:
    if sa.solicitacao_id:
        sol = db.get(SolicitacaoCorte, sa.solicitacao_id)
        if sol is not None:
            recalcular_solicitacao(db, sol)
    _avisar_se_cop_pronto(db, sa)


def avisar_financeiro(db: Session, texto: str, link: str) -> None:
    """Perfil Financeiro (spec v3.21 §6): linha de SA nova pede o R$/kg do precificador."""
    notificar(db, perfis=FINANCEIRO, tipo="SA_AGUARDANDO_PRECIFICADOR", texto=texto, link=link)


def tem_precificador(sa: CadastroSa | None) -> bool:
    """R$/kg do precificador preenchido na T14 (spec v3.16; zero conta como vazio, [proposta, P44(c)])."""
    return sa is not None and sa.rs_kg is not None and float(sa.rs_kg) > 0


def valor_precificador(sa: CadastroSa) -> float | None:
    """Valor precificador por peça: R$/kg × peso ÷ quantidade (T14)."""
    if sa.rs_kg and sa.peso_kg and sa.quantidade:
        return round(sa.rs_kg * sa.peso_kg / sa.quantidade, 2)
    return None


def pendencias_nf(db: Session, itens: list[CopItem]) -> tuple[list[CopItem], list[CopItem]]:
    """(itens sem SA confirmado, itens sem R$/kg). A NF do COP só libera sem nenhum dos dois (spec v3.16 T11)."""
    sem_sa: list[CopItem] = []
    sem_rs: list[CopItem] = []
    ids = [i.id for i in itens]
    # uma consulta só para todos os itens (antes era uma por item: N+1 no painel e nas listas de COP)
    por_item: dict[int, CadastroSa] = {}
    if ids:
        por_item = {s.cop_item_id: s for s in db.scalars(select(CadastroSa).where(CadastroSa.cop_item_id.in_(ids)))}
    for i in itens:
        sa = por_item.get(i.id)
        if sa is None or sa.situacao != "CONFIRMADO":
            sem_sa.append(i)
        if not tem_precificador(sa):
            sem_rs.append(i)
    return sem_sa, sem_rs


def frase_nf_bloqueada(sem_sa: int, sem_rs: int) -> str:
    falta = [x for x in (f"SA confirmado em {sem_sa} item(ns)" if sem_sa else "",
                         f"R$/kg do precificador em {sem_rs} item(ns)" if sem_rs else "") if x]
    return ("A NF de transferência só pode ser informada depois do SA confirmado e do R$/kg do precificador "
            f"(Cadastro de SA). Falta {' e '.join(falta)}.")


def _cop_pronto(db: Session, cop) -> bool:
    return cop.situacao == "FECHADO" and bool(cop.itens) and not any(pendencias_nf(db, list(cop.itens)))


def _avisar_se_cop_pronto(db: Session, sa: CadastroSa, *, antes: bool = False) -> None:
    """Avisa o RJ quando o COP fica com todos os SAs confirmados e todos os R$/kg (só na passagem)."""
    if not sa.cop_item_id:
        return
    db.flush()
    cop = db.get(CopItem, sa.cop_item_id).cop
    if not antes and _cop_pronto(db, cop):
        notificar(db, perfis=("OPERACAO_RJ",), tipo="COP_SA_PRONTO",
                  texto=f"COP {cop.numero}: todos os SAs e o precificador prontos. Informe a NF e envie.",
                  link=f"/cops/{cop.id}")


def obter_nf(db: Session, numero: str, emitente: str, data=None) -> NfTransferencia:
    numero = numero.strip()
    if not numero:
        raise ErroNegocio("Informe o número da NF.")
    if emitente not in EMITENTES_NOVOS:
        raise ErroNegocio("Emitente inválido: NF nova só da Fio Certo (FIO_CERTO).")
    nf = db.scalar(select(NfTransferencia).where(NfTransferencia.numero == numero,
                                                 NfTransferencia.emitente == emitente))
    if nf is None:
        nf = NfTransferencia(numero=numero, emitente=emitente, data=data)
        db.add(nf)
        db.flush()
    elif data and not nf.data:
        nf.data = data
    return nf


def informar_nf_b2(db: Session, ids: list[int], numero: str, emitente: str, data, *, usuario: Usuario,
                   ip: str | None) -> list[CadastroSa]:
    """Caminho B2: NF só fiscal, emitida no RJ e informada pelo Marcelo (Operação RJ) no SA; o Fabiano só recebe
    (Eduardo, 2026-11-19, pendências item 17). Várias linhas podem usar a mesma NF."""
    nf = obter_nf(db, numero, emitente, data)
    sas = [obter(db, i, travar=True) for i in ids]
    if any(sa.origem != "CORTE_ITU" for sa in sas):
        raise ErroNegocio("A NF do SA de COP é informada no COP, pelo RJ.")
    # spec v3.16 [proposta, P44(a)]: mesma trava da NF do COP (SA confirmado + R$/kg do precificador)
    sem_sa = sum(1 for sa in sas if sa.situacao != "CONFIRMADO")
    sem_rs = sum(1 for sa in sas if not tem_precificador(sa))
    if sem_sa or sem_rs:
        raise ErroNegocio(frase_nf_bloqueada(sem_sa, sem_rs))
    for sa in sas:
        sa.nf_id = nf.id
        _marcar_alteracao(db, sa)
    auditoria.registrar(db, "SA_NF_INFORMADA", usuario_id=usuario.id, entidade="sa",
                        entidade_id=",".join(map(str, ids)),
                        depois={"nf": numero, "emitente": emitente}, ip=ip)
    db.commit()
    return sas


def visivel(sa: CadastroSa, usuario: Usuario | None) -> bool:
    """[P10] Operação RJ vê os SAs de itens de COP e, desde 2026-11-19, os do corte em Itu (B2), porque é ela que
    informa a NF do B2 (pendências item 17); os da carga sem item de COP, não."""
    return (usuario is None or usuario.perfil != "OPERACAO_RJ" or sa.cop_item_id is not None
            or sa.origem == "CORTE_ITU")


def listar(db: Session, f: dict[str, Any], usuario: Usuario | None = None) -> list[CadastroSa]:
    q = select(CadastroSa)
    if usuario is not None and usuario.perfil == "OPERACAO_RJ":
        q = q.where(or_(CadastroSa.cop_item_id.is_not(None), CadastroSa.origem == "CORTE_ITU"))
    if f.get("situacao"):
        q = q.where(CadastroSa.situacao.in_(f["situacao"]))
    if f.get("origem"):
        q = q.where(CadastroSa.origem.in_(f["origem"]))
    if f.get("op"):
        q = q.where(CadastroSa.op == f["op"])
    if f.get("cop"):
        from app.models import Cop
        q = q.join(CopItem, CadastroSa.cop_item_id == CopItem.id).join(Cop, CopItem.cop_id == Cop.id).where(
            Cop.numero == f["cop"])
    if f.get("nao_exportados"):
        q = q.where(CadastroSa.exportado_renato_em.is_(None))
    # pendentes primeiro (do mais antigo, para fazer na ordem); confirmados depois, do mais novo para o mais antigo
    linhas = list(db.scalars(q))
    linhas.sort(key=lambda s: (s.situacao == "CONFIRMADO",
                               -s.data.toordinal() if s.situacao == "CONFIRMADO" else s.data.toordinal(),
                               -s.id if s.situacao == "CONFIRMADO" else s.id))
    return linhas


def para_dict(db: Session, sa: CadastroSa) -> dict[str, Any]:
    cop = sa.cop_item.cop if sa.cop_item else None
    valor = valor_precificador(sa)
    sug = sugerir(db, sa.item_codigo, exceto_id=sa.id) if sa.situacao != "CONFIRMADO" else None
    return {
        "id": sa.id, "origem": sa.origem, "situacao": sa.situacao, "data": sa.data.isoformat(), "op": sa.op,
        "cliente": sa.cliente, "item_codigo": sa.item_codigo, "item_descricao": sa.item_descricao, "pedido": sa.pedido,
        "material": sa.material, "dimensao": sa.dimensao, "conteiner": sa.conteiner, "quantidade": sa.quantidade,
        "peso_kg": sa.peso_kg, "rs_kg": sa.rs_kg, "valor_precificador": valor, "sa_codigo": sa.sa_codigo,
        "sa_codigo_sugerido": sa.sa_codigo_sugerido, "sa_novo": sa.sa_novo,
        "outros_codigos": sug.outros if sug else [], "sa_descricao": sa.sa_descricao, "ncm": sa.ncm, "icms": sa.icms,
        "ipi": sa.ipi, "nf": {"numero": sa.nf.numero, "emitente": sa.nf.emitente} if sa.nf else None,
        "cop": {"id": cop.id, "numero": cop.numero, "situacao": cop.situacao} if cop else None,
        "solicitacao_id": sa.solicitacao_id, "lote_id": sa.lote_id,
        "exportado_renato_em": sa.exportado_renato_em.isoformat() if sa.exportado_renato_em else None,
        "alterado_apos_exportar": sa.alterado_apos_exportar,
        "atrasado": atrasado(db, sa),
        "avisos": avisos(sa),
        "confirmacao_teste": bool((sa.dados_extra or {}).get("confirmacao_teste")),
        # spec v3.19: SA já achado no Mega que ainda não fechou por falta do R$/kg do precificador
        "sa_no_mega": sa.situacao != "CONFIRMADO" and sa_no_mega(sa),
        "precificador_obrigatorio": precisa_precificador(sa),
    }


def atrasado(db: Session, sa: CadastroSa) -> bool:
    """SA sem confirmação no Mega depois do prazo (padrão 48 h) aparece em vermelho no painel (§3.3)."""
    if sa.situacao == "CONFIRMADO":
        return False
    from .base import parametro
    criado = sa.criado_em if sa.criado_em.tzinfo else sa.criado_em.replace(tzinfo=agora().tzinfo)
    return agora() - criado > timedelta(hours=parametro(db, "PRAZO_CONFIRMACAO_SA_H"))


def validar_pendencias_cop(db: Session, cop) -> Resultado:
    r = Resultado()
    sem_sa, _ = pendencias_nf(db, list(cop.itens))
    if sem_sa:
        op = sem_sa[0].liberacao.solicitacao.op
        r.adicionar("SA_PENDENTE", Nivel.ERRO, f"Item da OP {op} ainda sem SA confirmado.")
    return r
