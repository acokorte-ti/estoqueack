# EstoqueACK — Tema visual padrão: layout A "Bancada"

Vale para **todas** as telas. Os valores ficam em `frontend/src/styles/tema.css`; as telas não definem cor, fonte ou tamanho próprios.
Histórico: tema inicial com as cores do site (Chat FRONTEND, 2026-10-29). Em 2026-11-19 o Eduardo escolheu o **layout A "Bancada"** entre três protótipos (A Bancada, B Linha, C Comando; os HTML ficam fora do repo, em `../layouts/`). A queixa que motivou a troca: botões escondidos, texto que era botão sem parecer, menu confuso, divs desalinhadas.

## De onde veio

- Da marca AçoKorte: o vermelho do logo (#EA1D26), o vermelho escuro dos títulos do site (#BE0A0F), o logo (`frontend/public/logo-acokorte.png`) e o aço escovado da tela de entrada.
- Do protótipo A: bancada clara (menu lateral claro, fundo cinza-claro, cartões brancos), fonte IBM Plex Sans no texto e IBM Plex Mono nos números, pílulas de situação com ícone.

## Cores

| Token | Cor | Uso |
|---|---|---|
| `--ack-vermelho` | #EA1D26 | Só marca. Nunca em texto pequeno |
| `--ack-vermelho-escuro` | #BE0A0F | **Botão principal**, barra do item ativo do menu, contador urgente, links (contraste 6,4:1 com branco) |
| `--aco-preto` / `--aco-grafite` | #1D1F22 / #33373C | Títulos e valores / texto |
| `--aco-medio` | #646A71 | Texto de apoio (5,4:1) |
| `--aco-borda` / `--aco-borda-clara` | #8A9096 / #C9CDD2 | Borda de botão e campo (visível no chão de fábrica) / botão pequeno e ícone |
| `--aco-linha` / `--aco-claro` / `--menu-fundo` | #E4E6E9 / #F3F4F6 / #FAFAFB | Divisórias / fundo da aplicação / menu lateral |
| `--estoque-mega` / `--estoque-rj-rio` / `--estoque-rj-itu` | azul / púrpura / bronze (com `-fundo` claro) | Significado fixo dos 3 estoques |
| `--bloqueio` / `--ciencia` / `--aviso` / `--sucesso` | vermelho / amarelo / cinza / verde | Validações (§5 da especificação), sempre com ícone e texto |
| `--foco` | #1F6FD1 | Anel de foco do teclado: azul, para não sumir em cima do vermelho |

**Vermelho de botão × vermelho de bloqueio:** o botão é sólido e diz o que faz. O bloqueio é sempre uma caixa ou pílula clara com ícone (✕, cadeado ou alerta) e texto. Não confundem.

## Tipografia

- **IBM Plex Sans** (400, 500, 600, 700) em tudo; h1 26 px, h2 18 px (16 px no cabeçalho de cartão).
- **IBM Plex Mono** (500, 600) em números: pesos, R$/kg, códigos de SA, OP, contadores. Alinhados à direita nas tabelas, para comparar de olho.
- Texto base de 15 px no computador e 16 px no tablet/celular (o iOS não amplia o campo ao tocar). As fontes vêm do pacote `@fontsource` (sem Google Fonts).

## Botões: todo botão tem cara de botão

| Classe | Aparência | Quando usar |
|---|---|---|
| `.primario` | Vermelho sólido, texto branco | **Um por tela**, à direita do cabeçalho: a ação que a tela existe para fazer |
| `.secundario` | Branco com contorno cinza de 1,5 px | Ações de apoio ("Exportar para Excel", "Sincronizar com o Mega") |
| `.perigo` | Branco com contorno vermelho | Desfazer ("Cancelar solicitação", "Estornar"). Nunca sólido |
| `.fantasma` | Sem contorno até passar o mouse | Ação discreta em cabeçalho de cartão ("Consultar →"), "Sair" |
| `.link` | Botão pequeno com contorno claro | Ação dentro de lista ou tabela ("Editar", "Remover"). **Não é mais texto sublinhado** |
| `.pequeno` | 34 px de altura | Botão dentro de tabela, cartão ou barra de ação em lote |
| `.falta` | Tracejado amarelo com ícone | Campo obrigatório ainda vazio, na própria coluna do dado ("Falta" no R$/kg, "Informar código") |
| `.valor` | Valor em fonte mono com lápis | Valor preenchido que pode ser corrigido, na própria coluna |

- **A ação fica na coluna do dado** (Cadastro de SA): não há coluna "Ações" longe do que se edita.
- **Ações em lote** aparecem numa barra escura embaixo, no centro, só quando há linhas marcadas (`.barra-lote`).
- **Altura mínima:** 44 px no computador, 48 px no tablet/celular (toque); botão pequeno 34/44 px. No celular o botão principal do rodapé tem 56 px.
- **Desabilitado:** cinza, com o cursor "proibido". A mensagem do motivo fica sempre visível.
- **Texto do botão:** verbo e objeto. Não usar "OK" nem "Enviar" sozinhos.
- **Abrir e fechar** (`details.avancado`, "Mais filtros"): contorno e seta que gira; não é texto solto.

## Situação: pílula com ícone e texto

`.etiqueta` virou pílula com ícone: `.ok` (✓ verde), `.atencao` (relógio, amarelo), `.ruim` (alerta, vermelho), `.bloqueio` (cadeado, vermelho), `.info` (i, azul), sem classe (i, cinza). Filtro de escolha única (`.chips[role="group"]`) vira controle segmentado; sem `role`, os botões de marcar ficam soltos.

## Campos

- **Tamanho e borda:** altura de 44/48 px, borda de 1,5 px, raio de 6 px, rótulo em negrito sempre acima do campo.
- **Escolha entre 2 e 4 opções:** botões grandes (`.opcao`), com a opção marcada em contorno preto de 2 px.

## Estrutura

- **Topo branco (60 px):** logo AçoKorte e "EstoqueACK" na largura do menu (o resto do topo começa na linha do conteúdo), "Pedir corte" (Estoque Itu e Admin), sino, usuário (iniciais, nome, perfil · planta) e "Sair".
- **Menu lateral claro (276 px), pelo caminho do material:** Hoje (Para fazer agora) → Corte (Pedir corte, Acompanhar pedidos, Cortes a fazer no RJ) → Envio RJ → Itu (Montar envio, Cadastro de SA, Receber em Itu) → Estoque (Consultar, Entrada por NF, Entradas do Mega sem lote, Conferir com o Mega) → Ferramentas → Administração. Ícone em cada item; o item ativo fica branco com barra vermelha.
- **Contador em cada item:** soma das pendências do Painel (`GET /api/painel/pendencias`, a mesma leitura, renovada a cada 2 min) cujo `link` abre aquela tela; vermelho quando alguma é ALERTA.
- **Esconder menu** (rodapé do menu, só no computador): fica a coluna de ícones (68 px), com o contador no canto do ícone; o navegador lembra a escolha.
- **Trilha** acima do título ("Envio RJ → Itu › Cadastro de SA"); numa tela de detalhe, o nome da lista é link de volta.
- **Cabeçalho da tela:** título, explicação curta e ações à direita, com uma linha embaixo.
- **Abaixo de 900 px:** o menu vira gaveta, aberta pelo botão de menu. Ela fecha com ✕, com Esc, tocando fora ou ao trocar de tela. Fechada, sai do Tab e do leitor de tela. Tabelas de chão de fábrica viram cartões.
- **Login e troca de senha:** fundo de aço escovado (o único lugar com o efeito) e um cartão branco com o logo e a faixa vermelha.

## Acessibilidade (piso)

- Contraste AA em todo texto.
- Foco visível em todo elemento clicável.
- Animação desligada quando o sistema pede movimento reduzido.
- Alvo de toque de pelo menos 48 px no tablet/celular (44 px no computador, com mouse).
- Cor nunca é a única pista: pílula tem ícone e texto; botão só de ícone tem `aria-label`; no menu escondido o nome do item continua para o leitor de tela e aparece ao passar o mouse.
