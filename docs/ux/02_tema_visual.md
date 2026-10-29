# EstoqueACK — Tema visual padrão (identidade AçoKorte)

Chat FRONTEND, 2026-10-29. Vale para **todas** as telas. Os valores ficam em `frontend/src/styles/tema.css`; as telas não definem cor, fonte ou tamanho próprios.

## De onde veio

Do site www.acokorte.com.br, conferido em 2026-10-29:

- o vermelho do logo (#EA1D26);
- o vermelho escuro dos títulos (#BE0A0F);
- o grafite dos botões e do texto (#3B3B3B);
- os cinzas claros (#F7F7F7 e #E1E1E1);
- as fontes Raleway (títulos) e Open Sans (texto);
- o fundo de aço escovado do topo do site.

O logo é o `logo-acokorte-positivo.png` do site, salvo em `frontend/public/logo-acokorte.png`.

## Cores

| Token | Cor | Uso |
|---|---|---|
| `--ack-vermelho` | #EA1D26 | Só marca: linha sob o topo, item ativo do menu, faixa do login. Nunca em texto pequeno |
| `--ack-vermelho-escuro` | #BE0A0F | **Botão principal** e links (contraste 6,4:1 com branco) |
| `--aco-preto` / `--aco-grafite` | #222 / #3B3B3B | Títulos / texto e botão secundário |
| `--aco-chumbo` | #2C2E31 | Menu lateral |
| `--aco-medio` | #6B7075 | Texto de apoio (5:1) |
| `--aco-borda` | #8A9096 | Borda de campo (3,2:1, visível no chão de fábrica) |
| `--aco-claro` | #F7F7F7 | Fundo |
| `--estoque-mega` / `--estoque-rj-rio` / `--estoque-rj-itu` | azul / púrpura / bronze | Significado fixo dos 3 estoques |
| `--bloqueio` / `--ciencia` / `--aviso` / `--sucesso` | vermelho / amarelo / cinza / verde | Validações (§5 da especificação), sempre com ícone e texto |
| `--foco` | #1F6FD1 | Anel de foco do teclado: azul, para não sumir em cima do vermelho |

**Vermelho de botão × vermelho de bloqueio:** o botão é sólido e diz o que faz. O bloqueio é sempre uma caixa clara com borda à esquerda, ícone ✕ e o texto "Bloqueia a operação". Não confundem.

## Tipografia

- Títulos em **Raleway 700**: h1 28 px, h2 20 px.
- Texto em **Open Sans** 400, 600 e 700, base de 16 px.
- Números sempre com algarismos tabulares. Peso em destaque em Open Sans 700, de 44 a 48 px.

## Botões (o mais importante para o operador)

| Classe | Aparência | Quando usar |
|---|---|---|
| `.primario` | Vermelho sólido, texto branco em negrito | **Um por tela**: a ação que a tela existe para fazer ("Confirmar corte", "Enviar ao RJ") |
| `.secundario` | Branco com contorno grafite de 2 px | Ações de apoio ("Conferir tolerância", "Exportar", "Sair") |
| `.perigo` | Branco com contorno vermelho | Desfazer ("Cancelar solicitação", "Estornar"). Nunca sólido |
| `.link` | Texto sublinhado | Ações dentro de tabela ("Redefinir senha") |
| `.bloco` | Largura total | Botão principal em formulário estreito ou no celular |

- **Altura mínima:** 48 px. No celular e no tablet, o botão principal do rodapé tem 56 px.
- **Desabilitado:** cinza, com o cursor "proibido". A mensagem do motivo fica sempre visível acima do botão.
- **Texto do botão:** verbo e objeto. Não usar "OK" nem "Enviar" sozinhos.

## Campos

- **Tamanho e borda:** altura de 48 px, borda de 1,5 px, rótulo em negrito sempre acima do campo.
- **Exemplos:** o placeholder fica em itálico cinza, para não ser confundido com um valor já preenchido.
- **Escolha entre 2 e 4 opções:** botões grandes (`.opcao`), com a opção marcada em contorno preto de 2 px.

## Estrutura

- **Topo branco:** logo AçoKorte e "EstoqueACK" à esquerda, usuário e botão "Sair" à direita, linha vermelha de 3 px embaixo.
- **Menu lateral:** chumbo, com uma faixa fina de aço escovado no alto. O item ativo tem barra vermelha à esquerda. Item que ainda não existe fica cinza, com "em breve".
- **Abaixo de 900 px:** o menu vira gaveta, aberta pelo botão "Menu". Ela fecha com ✕, com Esc, tocando fora ou ao trocar de tela. Quando está fechada, sai do Tab e do leitor de tela.
- **Login e troca de senha:** fundo de aço escovado (o único lugar com o efeito inteiro) e um cartão branco com o logo e a faixa vermelha.

## Acessibilidade (piso)

- Contraste AA em todo texto.
- Foco visível em todo elemento clicável.
- Animação desligada quando o sistema pede movimento reduzido.
- Alvo de toque de pelo menos 48 px.
- Cor nunca é a única pista.
