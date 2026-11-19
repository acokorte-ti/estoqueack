"""T05 "Entrada e documentos", "Completar dados da entrada" e documentos anexos (spec v3.15 T05, T06, T15,
"Documentos anexos"; contrato §16.4; migração 0012). Segue as propostas P41 e P42 até o Eduardo responder.

Onde o anexo fica ligado [proposta, P41(e)]: NF e packing list → entrada do lote de origem (sem entrada, o lote de
origem); precificador → contêiner (sem contêiner, o lote de origem); outro → o próprio lote. Lote filho (sobra, RETO,
peça inteira em Itu) mostra a entrada, o R$/kg e os anexos do lote de origem. Apagar só esconde [proposta, P41(d)].
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Anexo, AnexoArquivo, Conteiner, EntradaNf, EntradaNfItem, Lote, Movimento, Usuario

from . import auditoria
from .base import ErroNegocio, NaoEncontrado, agora, hoje, lote_visivel, parametro, so_rj_no_rio

TIPO_TEXTO = {"NF": "NF", "PACKING_LIST": "Packing list", "PRECIFICADOR": "Precificador do contêiner",
              "OUTRO": "Outro"}
# extensão → (Content-Type servido, assinaturas aceitas do começo do arquivo)
FORMATOS: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "pdf": ("application/pdf", (b"%PDF",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (b"PK\x03\x04",)),
    "xls": ("application/vnd.ms-excel", (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)),
}
SO_PRECIFICADOR = {"xls", "xlsx"}    # [proposta, P41(c)]: planilha só no precificador
MSG_TIPO = "Envie PDF, JPG ou PNG (no precificador, também XLS ou XLSX)."


# ---------------- campos ----------------

def digitos(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def ncm_ou_erro(v: str | None) -> str | None:
    """NCM com 8 dígitos (pontos e espaços opcionais); vazio é aceito [proposta, P42(c)]. None se vazio."""
    t = (v or "").strip()
    if not t:
        return None
    if not re.fullmatch(r"[\d.\s]+", t) or len(digitos(t)) != 8:
        raise ValueError(t)
    return digitos(t)


def ncm_valido(v: str | None) -> bool:
    try:
        ncm_ou_erro(v)
        return True
    except ValueError:
        return False


def texto(v: str | None, n: int) -> str | None:
    t = (v or "").strip()
    return t[:n] or None


def _mb(n: float) -> str:
    return f"{n:.1f}".replace(".", ",")


# ---------------- entrada do lote ----------------

def raiz(db: Session, lote: Lote) -> Lote:
    from .estoque import raiz as _raiz   # import tardio: estoque usa este módulo nos indicadores da T04
    return _raiz(db, lote)


def cadeia(db: Session, lote: Lote) -> list[Lote]:
    """O lote e os antepassados até o de origem (o último é a raiz)."""
    out, vistos, atual = [lote], {lote.id}, lote
    while atual.lote_pai_id is not None and atual.lote_pai_id not in vistos:
        atual = db.get(Lote, atual.lote_pai_id)
        out.append(atual)
        vistos.add(atual.id)
    return out


def item_da_entrada(db: Session, lote: Lote) -> EntradaNfItem | None:
    return db.scalar(select(EntradaNfItem).where(EntradaNfItem.lote_id == lote.id))


def custo_do_lote(db: Session, lote: Lote) -> float | None:
    """R$/kg que vale para o lote: o do item da entrada, senão o do lote, senão o da origem [proposta, P41(e)]."""
    for l in cadeia(db, lote):
        it = item_da_entrada(db, l)
        if it is not None and it.custo_kg is not None:
            return float(it.custo_kg)
        if l.custo_kg is not None:
            return float(l.custo_kg)
    return None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _primeira_data(db: Session, lote: Lote) -> date | None:
    return db.scalar(select(Movimento.data_referencia).where(Movimento.lote_id == lote.id)
                     .order_by(Movimento.id).limit(1))


def _carga(db: Session, lote: Lote) -> dict[str, Any] | None:
    ref = lote.origem_ref or {}
    if not ref or ref.get("origem") == "T15":
        return None
    data = lote.conteiner.data_entrada if lote.conteiner and lote.conteiner.data_entrada else _primeira_data(db, lote)
    return {"documento": lote.documento_entrada, "data_entrada": _iso(data),
            "custo_kg": float(lote.custo_kg) if lote.custo_kg is not None else None, "pecas": lote.pecas_iniciais,
            "peso_kg": round(float(lote.peso_inicial_kg), 3), "arquivo": ref.get("arquivo"), "aba": ref.get("aba"),
            "linha": ref.get("linha")}


def entrada_dict(db: Session, e: EntradaNf) -> dict[str, Any]:
    ct = db.get(Conteiner, e.conteiner_id) if e.conteiner_id else None
    return {"id": e.id, "numero": e.numero, "serie": e.serie, "data_emissao": _iso(e.data_emissao),
            "data_entrada": _iso(e.data), "fornecedor": e.fornecedor, "cnpj": e.cnpj, "chave_nfe": e.chave_nfe,
            "conteiner": ct.codigo if ct else None, "packing_list": e.packing_list, "di_duimp": e.di_duimp,
            "observacao": e.observacao}


def item_dict(it: EntradaNfItem) -> dict[str, Any]:
    return {"descricao_nf": it.descricao_nf, "ncm": it.ncm, "pecas": it.pecas, "peso_kg": round(float(it.peso_kg), 3),
            "peso_bruto_kg": float(it.peso_bruto_kg) if it.peso_bruto_kg is not None else None,
            "comprimento": it.comprimento, "custo_kg": float(it.custo_kg) if it.custo_kg is not None else None,
            "observacao": it.observacao}


def lote_visivel_ou_404(db: Session, lote_id: int, usuario: Usuario) -> Lote:
    l = db.get(Lote, lote_id)
    if l is None or not lote_visivel(usuario, l):
        raise NaoEncontrado("Lote não encontrado.")
    return l


def dados_da_entrada(db: Session, lote: Lote, usuario: Usuario) -> dict[str, Any]:
    """GET /api/lotes/{id}/entrada (T05 seção "Entrada e documentos")."""
    origem = raiz(db, lote)
    it = item_da_entrada(db, origem)
    e = it.entrada if it is not None else None
    carga = _carga(db, origem)
    return {"lote_id": lote.id, "da_origem": origem.codigo if origem.id != lote.id else None,
            "origem": e.origem if e is not None else ("CARGA" if carga else None),
            "entrada": entrada_dict(db, e) if e is not None else None,
            "item": item_dict(it) if it is not None else None,
            "carga": carga, "custo_kg": custo_do_lote(db, lote), "pode_completar": origem.id == lote.id,
            "anexos": anexos_do_lote(db, lote, usuario)}


# ---------------- "Completar dados da entrada" [proposta, P42(d)] ----------------

CAMPOS_CABECALHO = {"numero": 20, "serie": 5, "fornecedor": 120, "packing_list": 60, "di_duimp": 30,
                    "observacao": 500}


def _validar_completar(campos: dict[str, Any]) -> None:
    hj = hoje()
    if campos.get("data_emissao") is not None and campos["data_emissao"] > hj:
        raise ErroNegocio("A data de emissão não pode ser futura.")
    if campos.get("data_entrada") is not None and campos["data_entrada"] > hj:
        raise ErroNegocio("A data de entrada não pode ser futura.")
    if "ncm" in campos:
        try:
            campos["ncm"] = ncm_ou_erro(campos["ncm"])
        except ValueError:
            raise ErroNegocio("Informe o NCM com 8 dígitos (ex.: 7228.30.00).") from None
    for k in ("peso_bruto_kg", "custo_kg"):
        if campos.get(k) is not None and campos[k] < 0:
            raise ErroNegocio("O valor não pode ser negativo.")


def _entrada_para_completar(db: Session, lote: Lote, usuario: Usuario) -> EntradaNfItem:
    it = item_da_entrada(db, lote)
    if it is not None:
        return it
    data = (lote.conteiner.data_entrada if lote.conteiner and lote.conteiner.data_entrada else None) \
        or _primeira_data(db, lote) or lote.criado_em.date()
    # o nº da NF que a carga trouxe ("NF 99887") já entra na entrada nova
    m = re.match(r"\s*NF\s*([\w./-]{1,20})", lote.documento_entrada or "", re.IGNORECASE)
    e = EntradaNf(origem="T05", numero=m.group(1) if m else None, data=data, conteiner_id=lote.conteiner_id,
                  usuario_id=usuario.id)
    db.add(e)
    db.flush()
    it = EntradaNfItem(entrada_id=e.id, lote_id=lote.id, peso_kg=float(lote.peso_inicial_kg),
                       pecas=lote.pecas_iniciais, custo_kg=lote.custo_kg)
    db.add(it)
    db.flush()
    return it


def _para_json(v: Any) -> Any:
    if isinstance(v, date):
        return v.isoformat()
    if v is not None and not isinstance(v, str | int | bool):
        return float(v)
    return v


def completar_entrada(db: Session, lote_id: int, campos: dict[str, Any], *, usuario: Usuario,
                      ip: str | None) -> dict[str, Any]:
    """Corrige/completa o que NÃO mexe no saldo nem na identidade do lote (contêiner, liga, bitola, peso líquido,
    peças e comprimento continuam só por estorno, T18). Sem entrada, cria uma com origem T05."""
    lote = lote_visivel_ou_404(db, lote_id, usuario)
    origem = raiz(db, lote)
    if origem.id != lote.id:
        raise ErroNegocio(f"Este lote veio do lote {origem.codigo}. Complete os dados da entrada no lote de origem.")
    if not campos:
        raise ErroNegocio("Nada para mudar.")
    _validar_completar(campos)
    it = _entrada_para_completar(db, lote, usuario)
    e = it.entrada
    antes: dict[str, Any] = {}
    depois: dict[str, Any] = {}
    avisos: list[str] = []

    def mudar(obj: Any, attr: str, chave: str, novo: Any) -> None:
        velho = _para_json(getattr(obj, attr))
        if velho != _para_json(novo):
            antes[chave], depois[chave] = velho, _para_json(novo)
            setattr(obj, attr, novo)

    for k, n in CAMPOS_CABECALHO.items():
        if k in campos:
            mudar(e, k, k, texto(campos[k], n))
    for k, n, msg in (("cnpj", 14, "O CNPJ informado não tem 14 dígitos. Confira."),
                      ("chave_nfe", 44, "A chave de acesso da NF-e não tem 44 dígitos. Confira.")):
        if k in campos:
            d = digitos(campos[k]) or None
            if d and len(d) != n:
                avisos.append(msg)
            mudar(e, k, k, d[:14 if k == "cnpj" else 60] if d else None)
    if "data_emissao" in campos:
        mudar(e, "data_emissao", "data_emissao", campos["data_emissao"])
    if campos.get("data_entrada") is not None:
        mudar(e, "data", "data_entrada", campos["data_entrada"])
    if "descricao_nf" in campos:
        mudar(it, "descricao_nf", "descricao_nf", texto(campos["descricao_nf"], 200))
    if "observacao_item" in campos:
        mudar(it, "observacao", "observacao_item", texto(campos["observacao_item"], 500))
    for k in ("ncm", "peso_bruto_kg", "custo_kg"):
        if k in campos:
            mudar(it, k, k, campos[k])
    if "custo_kg" in campos:
        lote.custo_kg = campos["custo_kg"]          # o R$/kg do lote (T04, Excel, fechamento) acompanha o item
    if e.data_emissao and e.data and e.data < e.data_emissao:
        avisos.append("A data de entrada é anterior à emissão da NF. Confira.")
    if e.numero and not lote.documento_entrada:
        lote.documento_entrada = f"NF {e.numero}"[:60]
    db.flush()
    if depois:
        auditoria.registrar(db, "ENTRADA_COMPLETADA", usuario_id=usuario.id, entidade="lote", entidade_id=lote.id,
                            antes=antes, depois={**depois, "entrada_id": e.id}, ip=ip)
    db.commit()
    db.refresh(lote)
    r = dados_da_entrada(db, lote, usuario)
    r["avisos"] = avisos
    return r


# ---------------- anexos ----------------

def _nomes(db: Session, ids: set[int | None]) -> dict[int, str]:
    ok = {i for i in ids if i}
    return dict(db.execute(select(Usuario.id, Usuario.nome).where(Usuario.id.in_(ok))).all()) if ok else {}


def anexo_dict(a: Anexo, nomes: dict[int, str], da_origem: str | None = None) -> dict[str, Any]:
    ligado = "ENTRADA" if a.entrada_id else ("CONTEINER" if a.conteiner_id else "LOTE")
    return {"id": a.id, "tipo": a.tipo, "tipo_texto": TIPO_TEXTO.get(a.tipo, a.tipo), "descricao": a.descricao,
            "nome_arquivo": a.nome_arquivo, "content_type": a.content_type, "tamanho_bytes": a.tamanho_bytes,
            "ligado_a": ligado, "da_origem": da_origem, "usuario": nomes.get(a.usuario_id),
            "criado_em": a.criado_em.isoformat(), "apagado": a.apagado_em is not None,
            "apagado_por": nomes.get(a.apagado_por_id) if a.apagado_por_id else None,
            "apagado_em": a.apagado_em.isoformat() if a.apagado_em else None, "justificativa": a.justificativa_apagar}


def anexos_do_lote(db: Session, lote: Lote, usuario: Usuario) -> list[dict[str, Any]]:
    lotes = cadeia(db, lote)
    origem = lotes[-1]
    it = item_da_entrada(db, origem)
    conds = [Anexo.lote_id.in_([l.id for l in lotes])]
    if it is not None:
        conds.append(Anexo.entrada_id == it.entrada_id)
    conts = {l.conteiner_id for l in (lote, origem) if l.conteiner_id}
    if conts:
        conds.append(Anexo.conteiner_id.in_(conts))
    q = select(Anexo).where(or_(*conds))
    if usuario.perfil != "ADMIN":
        q = q.where(Anexo.apagado_em.is_(None))
    anexos = list(db.scalars(q.order_by(Anexo.criado_em.desc(), Anexo.id.desc())))
    nomes = _nomes(db, {a.usuario_id for a in anexos} | {a.apagado_por_id for a in anexos})
    filho = origem.id != lote.id
    return [anexo_dict(a, nomes, origem.codigo if filho and a.lote_id != lote.id else None) for a in anexos]


def _lotes_do_anexo(db: Session, a: Anexo) -> list[Lote]:
    if a.lote_id:
        return [db.get(Lote, a.lote_id)]
    if a.entrada_id:
        return list(db.scalars(select(Lote).join(EntradaNfItem, EntradaNfItem.lote_id == Lote.id)
                               .where(EntradaNfItem.entrada_id == a.entrada_id)))
    return list(db.scalars(select(Lote).where(Lote.conteiner_id == a.conteiner_id)))


def _pode_ver(usuario: Usuario, lotes: list[Lote]) -> bool:
    """[P10] Operação RJ só vê o que é de lote do RJ no Rio; os outros perfis veem tudo."""
    return not so_rj_no_rio(usuario) or any(lote_visivel(usuario, l) for l in lotes)


def anexo_ou_404(db: Session, anexo_id: int, usuario: Usuario, *, incluir_apagado: bool = False) -> Anexo:
    a = db.get(Anexo, anexo_id)
    if a is None or not _pode_ver(usuario, _lotes_do_anexo(db, a)):
        raise NaoEncontrado("Documento não encontrado.")
    if a.apagado_em is not None and not (incluir_apagado or usuario.perfil == "ADMIN"):
        raise NaoEncontrado("Documento não encontrado.")
    return a


def conteudo(db: Session, a: Anexo) -> bytes:
    arq = db.get(AnexoArquivo, a.id)
    if arq is None:
        raise NaoEncontrado("Arquivo não encontrado.")
    return bytes(arq.conteudo)


def conferir_tamanho(db: Session, tamanho: int) -> None:
    """ANEXO_GRANDE: maior que ANEXO_MAX_MB (T23, padrão 10) bloqueia."""
    mb = parametro(db, "ANEXO_MAX_MB")
    if tamanho > mb * 1024 * 1024:
        raise ErroNegocio(f"O arquivo tem {_mb(tamanho / 1024 / 1024)} MB; o limite é {mb:g} MB. "
                          "Escaneie com resolução menor ou divida o PDF.")


def _nome_limpo(nome: str | None) -> str:
    base = re.split(r"[\\/]", (nome or "").strip())[-1]
    base = re.sub(r"[\x00-\x1f\x7f\"<>|*?:]", "", base).strip(" .")
    return base[:200]


def _novo(db: Session, *, tipo: str, nome: str | None, descricao: str | None, dados: bytes, alvo: dict[str, int],
          usuario: Usuario, ip: str | None, onde: dict[str, Any]) -> dict[str, Any]:
    if tipo not in TIPO_TEXTO:
        raise ErroNegocio("Tipo de documento inválido. Use NF, packing list, precificador ou outro.")
    desc = texto(descricao, 120)
    if tipo == "OUTRO" and not desc:
        raise ErroNegocio('Descreva o documento do tipo "Outro".')
    nome_ok = _nome_limpo(nome)
    if not dados:
        raise ErroNegocio("O arquivo está vazio.")
    conferir_tamanho(db, len(dados))
    m = re.search(r"\.([A-Za-z0-9]{1,5})$", nome_ok)
    ext = m.group(1).lower() if m else ""
    fmt = FORMATOS.get(ext)
    if fmt is None or (ext in SO_PRECIFICADOR and tipo != "PRECIFICADOR") or not dados.startswith(fmt[1]):
        raise ErroNegocio(MSG_TIPO)
    a = Anexo(tipo=tipo, descricao=desc, nome_arquivo=nome_ok, content_type=fmt[0], tamanho_bytes=len(dados),
              sha256=hashlib.sha256(dados).hexdigest(), usuario_id=usuario.id, **alvo)
    db.add(a)
    db.flush()
    db.add(AnexoArquivo(anexo_id=a.id, conteudo=dados))
    auditoria.registrar(db, "ANEXO_CRIADO", usuario_id=usuario.id, entidade="anexo", entidade_id=a.id,
                        depois={"tipo": tipo, "nome": nome_ok, "tamanho_bytes": len(dados), "sha256": a.sha256,
                                **alvo, **onde}, ip=ip)
    db.commit()
    return anexo_dict(a, {usuario.id: usuario.nome})


def anexar_no_lote(db: Session, lote_id: int, *, tipo: str, nome: str | None, descricao: str | None, dados: bytes,
                   usuario: Usuario, ip: str | None) -> dict[str, Any]:
    lote = lote_visivel_ou_404(db, lote_id, usuario)
    origem = raiz(db, lote)
    if tipo in ("NF", "PACKING_LIST"):
        it = item_da_entrada(db, origem)
        alvo = {"entrada_id": it.entrada_id} if it is not None else {"lote_id": origem.id}
    elif tipo == "PRECIFICADOR":
        ct = lote.conteiner_id or origem.conteiner_id
        alvo = {"conteiner_id": ct} if ct else {"lote_id": origem.id}
    else:
        alvo = {"lote_id": lote.id}
    return _novo(db, tipo=tipo, nome=nome, descricao=descricao, dados=dados, alvo=alvo, usuario=usuario, ip=ip,
                 onde={"pelo_lote": lote.codigo})


def anexar_na_entrada(db: Session, entrada_id: int, *, tipo: str, nome: str | None, descricao: str | None,
                      dados: bytes, usuario: Usuario, ip: str | None) -> dict[str, Any]:
    e = db.get(EntradaNf, entrada_id)
    lotes = list(db.scalars(select(Lote).join(EntradaNfItem, EntradaNfItem.lote_id == Lote.id)
                            .where(EntradaNfItem.entrada_id == entrada_id))) if e is not None else []
    if e is None or not _pode_ver(usuario, lotes):
        raise NaoEncontrado("Entrada não encontrada.")
    alvo = {"conteiner_id": e.conteiner_id} if tipo == "PRECIFICADOR" and e.conteiner_id else {"entrada_id": e.id}
    return _novo(db, tipo=tipo, nome=nome, descricao=descricao, dados=dados, alvo=alvo, usuario=usuario, ip=ip,
                 onde={"pela_entrada": e.id})


def apagar(db: Session, anexo_id: int, justificativa: str, *, usuario: Usuario, ip: str | None) -> dict[str, Any]:
    j = (justificativa or "").strip()
    if not j:   # sem mínimo de caracteres (spec v3.14 §9, Eduardo, 2026-11-17)
        raise ErroNegocio("Escreva a justificativa.")
    a = anexo_ou_404(db, anexo_id, usuario)
    if a.apagado_em is not None:
        raise ErroNegocio("Este documento já foi apagado.")
    a.apagado_em, a.apagado_por_id, a.justificativa_apagar = agora(), usuario.id, j[:500]
    auditoria.registrar(db, "ANEXO_APAGADO", usuario_id=usuario.id, entidade="anexo", entidade_id=a.id,
                        depois={"nome": a.nome_arquivo, "justificativa": j[:500]}, ip=ip)
    db.commit()
    return anexo_dict(a, _nomes(db, {a.usuario_id, a.apagado_por_id}))


def restaurar(db: Session, anexo_id: int, *, usuario: Usuario, ip: str | None) -> dict[str, Any]:
    a = anexo_ou_404(db, anexo_id, usuario, incluir_apagado=True)
    if a.apagado_em is None:
        raise ErroNegocio("Este documento não está apagado.")
    antes = {"apagado_em": a.apagado_em.isoformat(), "justificativa": a.justificativa_apagar}
    a.apagado_em, a.apagado_por_id, a.justificativa_apagar = None, None, None
    auditoria.registrar(db, "ANEXO_RESTAURADO", usuario_id=usuario.id, entidade="anexo", entidade_id=a.id,
                        antes=antes, depois={"nome": a.nome_arquivo}, ip=ip)
    db.commit()
    return anexo_dict(a, _nomes(db, {a.usuario_id}))


# ---------------- indicadores da T04 e do Excel ----------------

class MapaAnexos:
    """Quais lotes têm anexo (e precificador), lendo a tabela de anexos uma vez só (T04 sem N+1)."""

    def __init__(self, db: Session):
        linhas = db.execute(select(Anexo.tipo, Anexo.lote_id, Anexo.entrada_id, Anexo.conteiner_id)
                            .where(Anexo.apagado_em.is_(None))).all()
        entradas = {r.entrada_id for r in linhas if r.entrada_id}
        lotes_da_entrada: dict[int, set[int]] = {}
        if entradas:
            for ent, lid in db.execute(select(EntradaNfItem.entrada_id, EntradaNfItem.lote_id)
                                       .where(EntradaNfItem.entrada_id.in_(entradas))):
                lotes_da_entrada.setdefault(ent, set()).add(lid)
        self.lotes: dict[str, set[int]] = {"*": set(), "PRECIFICADOR": set()}
        self.conts: dict[str, set[int]] = {"*": set(), "PRECIFICADOR": set()}
        for r in linhas:
            for k in ["*"] + (["PRECIFICADOR"] if r.tipo == "PRECIFICADOR" else []):
                if r.lote_id:
                    self.lotes[k].add(r.lote_id)
                if r.entrada_id:
                    self.lotes[k] |= lotes_da_entrada.get(r.entrada_id, set())
                if r.conteiner_id:
                    self.conts[k].add(r.conteiner_id)

    def tem(self, lote: Lote, origem: Lote | None = None, tipo: str = "*") -> bool:
        return any(l.id in self.lotes[tipo] or (l.conteiner_id is not None and l.conteiner_id in self.conts[tipo])
                   for l in (lote, origem) if l is not None)
