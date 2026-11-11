"""T14 SA: fila, sugestão do código pelo item da peça acabada, código informado, confirmação no Mega e
exportações. As linhas nascem do COP fechado (caminhos A e B) e do corte em Itu de lote fiscal RJ (B2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.formato import kg_br, pct_br
from app.domain.validacao import Nivel, Resultado
from app.integrations.mega import fabrica
from app.models import CadastroSa, CopItem, Lote, NfTransferencia, SolicitacaoCorte, Usuario

from . import auditoria
from .base import ErroNegocio, NaoEncontrado, Previa, agora, exigir_sem_pendencias, notificar, parametro
from .estoque import bitola
from .fluxo import recalcular_solicitacao

EMITENTES = ("FIO_CERTO", "MEDIO_VALE", "OUTRO")


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
    except Exception:  # noqa: BLE001
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
    antes = {c: getattr(sa, c) for c in dados}
    for c, v in dados.items():
        if c in CAMPOS_EDITAVEIS:
            setattr(sa, c, v)
    _marcar_alteracao(db, sa)
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
    entrada na filial 3, em peças) a partir da data do SA − SA_JANELA_ANTES_DIAS (7). Ver consultas.SITUACAO_SA."""
    janela = _janela(db)
    try:
        g = fabrica.obter()
    except fabrica.MegaIndisponivel as e:
        return {"verificados": 0, "confirmados": 0, "erro": str(e)}
    confirmados = 0
    for sa in sas:
        if sa.situacao != "AGUARDANDO_MEGA" or not sa.sa_codigo:
            continue
        try:
            st = g.situacao_sa(sa.sa_codigo, sa.data - timedelta(days=janela))
        except Exception as e:  # noqa: BLE001
            return {"verificados": 0, "confirmados": confirmados, "erro": f"Erro no Mega ({type(e).__name__})"}
        sa.verificado_mega_em = agora()
        if st is not None and st.existe and st.ativo is not False and st.qtd_entrada > 0:
            sa.situacao, sa.confirmado_em = "CONFIRMADO", agora()
            if st.descricao and not sa.sa_descricao:
                sa.sa_descricao = st.descricao
            if st.ncm and not sa.ncm:
                sa.ncm = st.ncm
            if st.ipi_pct is not None and not sa.ipi:
                sa.ipi = f"{st.ipi_pct / 100:.4g}"
            sa.dados_extra = {**(sa.dados_extra or {}),
                              "mega": {"qtd_entrada": st.qtd_entrada, "nf_entrada": st.nf_entrada,
                                       "ncm": st.ncm, "ipi_pct": st.ipi_pct}}
            confirmados += 1
            _ao_confirmar(db, sa)
    db.flush()
    return {"verificados": len(sas), "confirmados": confirmados, "erro": None}


def _ao_confirmar(db: Session, sa: CadastroSa) -> None:
    if sa.solicitacao_id:
        sol = db.get(SolicitacaoCorte, sa.solicitacao_id)
        if sol is not None:
            recalcular_solicitacao(db, sol)
    if sa.cop_item_id:
        item = db.get(CopItem, sa.cop_item_id)
        pend = [i for i in item.cop.itens if not _sa_confirmado(db, i)]
        if not pend:
            notificar(db, perfis=("OPERACAO_RJ",), tipo="COP_SA_PRONTO",
                      texto=f"COP {item.cop.numero}: todos os SAs prontos. Informe a NF e envie.",
                      link=f"/cops/{item.cop.id}")


def _sa_confirmado(db: Session, item: CopItem) -> bool:
    sa = db.scalar(select(CadastroSa).where(CadastroSa.cop_item_id == item.id))
    return sa is not None and sa.situacao == "CONFIRMADO"


def obter_nf(db: Session, numero: str, emitente: str, data=None) -> NfTransferencia:
    numero = numero.strip()
    if not numero:
        raise ErroNegocio("Informe o número da NF.")
    if emitente not in EMITENTES:
        raise ErroNegocio("Emitente inválido (FIO_CERTO, MEDIO_VALE ou OUTRO).")
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
    """Caminho B2: NF só fiscal digitada pelo Fabiano no SA (várias linhas podem usar a mesma NF)."""
    nf = obter_nf(db, numero, emitente, data)
    sas = [obter(db, i, travar=True) for i in ids]
    for sa in sas:
        if sa.origem != "CORTE_ITU":
            raise ErroNegocio("A NF do SA de COP é informada no COP, pelo RJ.")
        sa.nf_id = nf.id
        _marcar_alteracao(db, sa)
    auditoria.registrar(db, "SA_NF_INFORMADA", usuario_id=usuario.id, entidade="sa",
                        entidade_id=",".join(map(str, ids)),
                        depois={"nf": numero, "emitente": emitente}, ip=ip)
    db.commit()
    return sas


def visivel(sa: CadastroSa, usuario: Usuario | None) -> bool:
    """[P10] Operação RJ vê só os SAs de itens de COP (RJ no Rio); SA de corte em Itu (B2) e sem item de COP não."""
    return usuario is None or usuario.perfil != "OPERACAO_RJ" or sa.cop_item_id is not None


def listar(db: Session, f: dict[str, Any], usuario: Usuario | None = None) -> list[CadastroSa]:
    q = select(CadastroSa)
    if usuario is not None and usuario.perfil == "OPERACAO_RJ":
        q = q.where(CadastroSa.cop_item_id.is_not(None))
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
    valor = round(sa.rs_kg * sa.peso_kg / sa.quantidade, 2) if sa.rs_kg and sa.peso_kg and sa.quantidade else None
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
    for i in cop.itens:
        if not _sa_confirmado(db, i):
            r.adicionar("SA_PENDENTE", Nivel.ERRO, f"Item da OP {i.liberacao.solicitacao.op} ainda sem SA confirmado.")
            break
    return r
