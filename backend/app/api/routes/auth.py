from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.schemas import (LoginEntrada, RecuperarEntrada, RedefinirSenhaEntrada, SessaoSaida, TokenEntrada,
                             TrocaSenhaEntrada, UsuarioSaida)
from app.core.config import Config
from app.core.db import get_db
from app.models import Sessao
from app.services import auth, email, recuperacao

router = APIRouter(prefix="/auth", tags=["autenticação"])


def _gravar_cookies(resp: Response, cfg: Config, token: str, csrf: str, max_age: int) -> None:
    seguro = cfg.producao
    resp.set_cookie(deps.COOKIE_SESSAO, token, max_age=max_age, httponly=True, secure=seguro,
                    samesite="strict", path="/api")
    # CSRF legível pelo front-end (double-submit): enviado de volta no header X-CSRF-Token
    resp.set_cookie(deps.COOKIE_CSRF, csrf, max_age=max_age, httponly=False, secure=seguro,
                    samesite="strict", path="/")


@router.post("/login", response_model=SessaoSaida)
def login(dados: LoginEntrada, request: Request, response: Response,
          db: Session = Depends(get_db), cfg: Config = Depends(deps.config)):
    try:
        s = auth.autenticar(db, cfg, dados.login, dados.senha, deps.ip_cliente(request),
                            request.headers.get("user-agent"), lembrar=dados.lembrar)
    except auth.ErroAutenticacao as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from None
    duracao = cfg.sessao_lembrar_dias * 86400 if dados.lembrar else cfg.sessao_horas * 3600
    _gravar_cookies(response, cfg, s.token, s.csrf, duracao)
    return SessaoSaida(usuario=UsuarioSaida.model_validate(s.usuario), csrf=s.csrf, expira_em=s.expira_em)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, sessao: Sessao = Depends(deps.sessao_atual),
           db: Session = Depends(get_db)):
    auth.encerrar(db, sessao, deps.ip_cliente(request))
    response.delete_cookie(deps.COOKIE_SESSAO, path="/api")
    response.delete_cookie(deps.COOKIE_CSRF, path="/")


@router.get("/eu", response_model=SessaoSaida)
def eu(sessao: Sessao = Depends(deps.sessao_atual)):
    return SessaoSaida(usuario=UsuarioSaida.model_validate(sessao.usuario), csrf=sessao.csrf,
                       expira_em=sessao.expira_em)


@router.post("/trocar-senha", status_code=204)
def trocar_senha(dados: TrocaSenhaEntrada, request: Request, sessao: Sessao = Depends(deps.sessao_atual),
                 db: Session = Depends(get_db), cfg: Config = Depends(deps.config)):
    try:
        auth.trocar_senha(db, cfg, sessao.usuario, dados.senha_atual, dados.nova_senha, sessao.id,
                          deps.ip_cliente(request))
    except auth.ErroAutenticacao as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None


# ---------------- Recuperação de senha por e-mail ----------------

@router.post("/recuperar", status_code=202)
def recuperar(dados: RecuperarEntrada, request: Request, tarefas: BackgroundTasks, db: Session = Depends(get_db),
              cfg: Config = Depends(deps.config)) -> dict:
    """Sempre responde a mesma mensagem (não revela se o login/e-mail existe). O e-mail sai em segundo plano."""
    pedido = recuperacao.solicitar(db, cfg, dados.identificador, deps.ip_cliente(request))
    if pedido is not None:
        assunto, texto, html = recuperacao.texto_email(cfg, pedido.usuario.nome.split(" ")[0], pedido.link)
        tarefas.add_task(email.enviar, cfg, pedido.usuario.email, assunto, texto, html)
    return {"mensagem": recuperacao.MENSAGEM_PADRAO}


@router.post("/recuperar/verificar")
def verificar_link(dados: TokenEntrada, db: Session = Depends(get_db)) -> dict:
    u = recuperacao.verificar(db, dados.token)
    if u is None:
        return {"valido": False, "mensagem": "Link inválido ou expirado. Peça um novo em \"Esqueci minha senha\"."}
    return {"valido": True, "login": u.login}


@router.post("/recuperar/redefinir", status_code=204)
def redefinir_por_link(dados: RedefinirSenhaEntrada, request: Request, db: Session = Depends(get_db),
                       cfg: Config = Depends(deps.config)):
    try:
        recuperacao.redefinir(db, cfg, dados.token, dados.nova_senha, deps.ip_cliente(request))
    except auth.ErroAutenticacao as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
