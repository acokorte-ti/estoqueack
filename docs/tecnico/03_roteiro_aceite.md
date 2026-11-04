# Roteiro de aceite da Fase 1 (qui 12/11/2026, manhã)

Escrito em 2026-11-03 pelo chat BANCO E TESTES. Usado no aceite com **Fabiano, Matheus, Marcelo e Renato**, antes do go/no-go de 12/11 (ver `coordenacao/ESTADO_COORDENACAO.md` §5). Cada pessoa usa o **próprio login**, no próprio computador ou tablet, em https://estoque.acokorte.com.br (só da rede da empresa).

## 0. Antes do aceite (Eduardo + BANCO E TESTES, até qua 11/11)

| # | Item | Quem | Ok |
|---|---|---|---|
| 0.1 | Carga T25 feita na homologação e conferida pelo Fabiano (soma dos lotes por código = saldo Mega ± 5 kg; total RJ = ESTOQUE 2026) | TÉCNICO + Fabiano | ☐ |
| 0.2 | Usuários reais criados (T21): `fabiano.camargo`, `matheus.almeida`, `marcello.teixeira`, `renato.pinto`, cada um com e-mail e perfil certo (Estoque Itu, Estoque Itu, Operação RJ, Análise) | Eduardo | ☐ |
| 0.3 | Cada um entrou uma vez e trocou a senha temporária | cada um | ☐ |
| 0.4 | Ponta a ponta automático dos 5 caminhos rodado sem erro (`deploy/e2e/rodar_e2e.sh`; 1º ensaio OK em 04/11; repetir qua 11/11) | BANCO E TESTES | ☐ |
| 0.5 | "Mega atualizado em …" de hoje no Painel (sincronização das 06h OK) | — | ☐ |
| 0.6 | Escolher **OPs reais abertas** para o aceite (uma por caminho) e os lotes da carga que vão ser usados. Ficam anotadas na tabela do §6 | Fabiano + BANCO E TESTES | ☐ |

**Importante:** tudo o que for feito no aceite fica gravado (o sistema não apaga movimentos). Para desfazer um teste, usa-se **estorno** (T18), como no uso real. Por isso o aceite usa quantidades pequenas e, ao final, o BANCO E TESTES estorna o que foi criado só para teste (§5).

Como registrar um problema: anote na tabela do §7 **a tela, o que fez, o que esperava e o que aconteceu** (se puder, tire um print). Não precisa resolver na hora.

## 1. Fabiano e Matheus (Estoque Itu)

### 1.1 Entrar e conferir o estoque

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | Entrar com o seu login | Painel com a barra de estoque e "Mega atualizado em …" | ☐ |
| 2 | **T04 Consulta de estoque**: filtrar por uma liga que você conhece (ex.: H13) | Os lotes da carga, separados em *RJ no Rio*, *RJ em Itu* e *Estoque Mega*, com saldo e reservado | ☐ |
| 3 | Abrir um lote **RJ no Rio** (T05) | Contêiner, bitola, saldo, extrato de movimentos com a origem na planilha (aba e linha) | ☐ |
| 4 | Conferir 2 lotes que você sabe o saldo de cabeça | Saldo igual ao da ESTOQUE 2026 | ☐ |

### 1.2 Caminho A — corte no RJ (com o Marcelo)

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | **T07 Nova solicitação**: digitar a OP do §6 (caminho A) | Item, cliente, pedido e situação **Aberta** vindos do Mega; a estrutura da OP mostra o SA | ☐ |
| 2 | Escolher a liga e a medida acabada; ver os lotes compatíveis | Lotes que comportam a medida, com sobremetal %; liga equivalente com selo | ☐ |
| 3 | Escolher um lote RJ no Rio, modo **Cortar no RJ**, quantidade e prazo | Peso previsto calculado (bitola + sobremetal 5 mm) e a frase do que vai acontecer | ☐ |
| 4 | **Enviar ao RJ** | Solicitação **Enviada**; o peso previsto aparece como **reservado** no lote | ☐ |
| 5 | (depois do Marcelo cortar e fechar o COP) **T14 SA** | Linha do SA com material, dimensão, contêiner, peças e **peso real**; código sugerido (o da estrutura da OP) | ☐ |
| 6 | Fazer no Mega o cadastro/carga do SA como hoje; informar o código no sistema | Fica **Aguardando Mega**; em até 30 min (ou "Verificar no Mega agora") vira **Confirmado** | ☐ |
| 7 | (depois do Marcelo enviar) **T12 Receber COP**: conferir e confirmar | COP **Recebido**; solicitação **Concluída** | ☐ |

### 1.3 Caminho B — peça inteira (com o Marcelo)

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | T07 com a OP do §6 (caminho B), modo **Trazer peça inteira** | Peso previsto da peça (bitola + sobremetal), não da barra | ☐ |
| 2 | (depois do Marcelo separar a barra, fechar o COP e enviar) T14: o SA vem com o **peso previsto** | SA com o previsto, não com o peso da barra | ☐ |
| 3 | T12: receber | Nasce um lote **RJ em Itu** com o peso da barra; solicitação **Aguardando corte em Itu** | ☐ |
| 4 | **T13 Corte em Itu**: consumo, sobra e se a sobra ficou na bitola | Perda calculada; sobra fora da bitola vira lote **RETO**; solicitação **Concluída** | ☐ |
| 5 | Pôr um consumo **mais de 5 %** acima do previsto | Pede justificativa (amarelo); com justificativa, grava | ☐ |

### 1.4 Caminho B2 — corte em Itu de material RJ que já está em Itu

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | T13 com a OP do §6 (caminho B2) e um lote **RJ em Itu** da carga | Consumo baixa o lote; aparece a linha nova na **fila de SA** | ☐ |
| 2 | T14: informar o código do SA e a **NF só fiscal** | SA com a NF; aviso cinza se a NF for diferente da entrada no Mega | ☐ |

### 1.5 Caminho C — material Mega

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | T13 com a OP do §6 (caminho C) e um lote **Estoque Mega** | Instrução "**Fazer no Mega**" pronta (baixar X kg do código na OP; transferir a sobra para o código RETO) | ☐ |
| 2 | Copiar a instrução e fazer no Mega como hoje | Na sincronização seguinte (ou "Sincronizar agora"), o saldo Mega bate com o lote | ☐ |

### 1.6 Rede de segurança

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | **T17**: criar uma reserva de 10 kg num lote | O disponível do lote cai 10 kg; numa solicitação nova aparece o aviso de reserva | ☐ |
| 2 | **T18 Estorno**: estornar um movimento de teste, com justificativa | O saldo volta; o movimento original e o estorno continuam no extrato (nada é apagado) | ☐ |
| 3 | **T18 Ajuste**: contar um lote e informar o saldo contado | Movimento de ajuste com justificativa | ☐ |
| 4 | Tentar uma solicitação com OP **encerrada** | Bloqueia (vermelho) | ☐ |
| 5 | Tentar uma OP **Firme planejada / Liberada** | Só avisa (cinza) e deixa seguir | ☐ |

## 2. Marcelo (Operação RJ)

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | Entrar no tablet/computador do RJ | Menu só com as telas do RJ; **só lotes RJ no Rio** | ☐ |
| 2 | **T06 Entrada por NF** (caminho D): NF de teste com 1 item | Nasce um lote RJ no Rio com o saldo informado; NF repetida é bloqueada | ☐ |
| 3 | **T09 Fila RJ**: abrir a solicitação do caminho A do Fabiano | Aparece com prazo, OP, lote, quantidade e instrução de corte | ☐ |
| 4 | **T10 Registrar corte**: peças e peso real | Baixa o lote; solicitação **Cortada**; o Fabiano recebe aviso no sino | ☐ |
| 5 | Repetir com **"Usar outro lote / dividir"** (dois lotes) | Pede justificativa; os dois lotes são baixados | ☐ |
| 6 | Pôr um peso **mais de 5 %** acima do previsto | Pede justificativa | ☐ |
| 7 | Caminho B: separar a barra e informar o **peso da barra inteira** | Aceita sem a regra dos 5 % | ☐ |
| 8 | **T11 COP**: novo COP, adicionar os cortes prontos, **Fechar COP** | Os SAs vão para a fila do Fabiano; "SAs confirmados X de N" | ☐ |
| 9 | Tentar **Enviar** antes de todos os SAs confirmados | Bloqueia ("SA pendente") | ☐ |
| 10 | Com os SAs confirmados: informar a **NF** (uma para o COP) e **Enviar** | COP **Enviado**; solicitações **Em trânsito** | ☐ |
| 11 | Estornar um corte seu **antes** de entrar no COP | Solicitação volta para **Enviada** e o saldo volta | ☐ |

## 3. Renato (Análise)

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | Entrar | Painel; pode consultar estoque, solicitações, COPs e SAs, sem botões de alterar | ☐ |
| 2 | **T14 SA**: filtrar os SAs do aceite | Linhas com OP, cliente, item, material, contêiner, peso, código e NF | ☐ |
| 3 | Informar o **R$/kg** de um SA | Grava (só o R$/kg; o resto fica travado para ele) | ☐ |
| 4 | **T17**: criar uma reserva | Permitido para Análise | ☐ |
| 5 | "Sincronizar agora" | Atualiza "Mega atualizado em …" | ☐ |

## 4. Todos

| Passo | O que fazer | O que deve ver | Ok |
|---|---|---|---|
| 1 | **T20 Calculadora**: bitola + comprimento + quantidade | Peso igual ao da planilha "calculo de peso" | ☐ |
| 2 | Sino de avisos | Avisos do seu perfil (ex.: Fabiano recebe "corte registrado") | ☐ |
| 3 | "Esqueci minha senha" | E-mail chega com o link | ☐ |

## 5. Depois do aceite (BANCO E TESTES)

1. Estornar os movimentos criados só para teste (T18), com a justificativa "Teste de aceite 12/11".
2. Cancelar as solicitações de teste que não foram usadas; os COPs/SAs de teste ficam marcados com "TESTE" na observação.
3. Conferir de novo: soma dos lotes por código = saldo Mega ± 5 kg.
4. Passar a lista do §7 para a COORDENAÇÃO (o que é bloqueio para 13/11 e o que vira ressalva).

## 6. Dados do aceite (preencher até qua 11/11)

| Caminho | OP real (aberta) | Item / cliente | Lote da carga | Quem |
|---|---|---|---|---|
| A — corte no RJ | | | RJ no Rio: | Fabiano + Marcelo |
| B — peça inteira | | | RJ no Rio: | Matheus + Marcelo |
| B2 — RJ em Itu | | | RJ em Itu: | Fabiano |
| C — material Mega | | | Estoque Mega (código): | Matheus |
| D — entrada NF RJ | — | — | (lote novo) | Marcelo |

## 7. Problemas encontrados

| # | Quem | Tela | O que fez | Esperava | Aconteceu | Bloqueia 13/11? |
|---|---|---|---|---|---|---|
| | | | | | | |

## 8. Critério de aceite

O aceite passa se **os 5 caminhos** (§1.2–1.5 e §2) foram feitos do começo ao fim sem erro que impeça continuar, se o **estorno e o ajuste** (§1.6) funcionaram e se **cada um dos 4** entrou com o próprio login e viu só as telas do seu perfil. Problemas de texto, layout ou conforto viram ressalva com data, sem segurar a implantação.
