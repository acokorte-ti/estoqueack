# EstoqueACK — Guia de UX do frontend

Chat FRONTEND, 2026-10-29. Base: telas T01–T25 de `03_Especificacao_Funcional.md` (pedido R002).
Este guia define **como** as telas se comportam visualmente. **O que** cada tela tem (campos, botões, regras) continua vindo só da especificação funcional. Onde a especificação não responde, há pedido aberto em `coordenacao/PEDIDOS.md` (R003–R010) e a tela fica com o ponto marcado como pendente.

## 1. Para quem é

Operador de chão de fábrica (Marcelo no RJ, Fabiano e Matheus em Itu), muitas vezes de pé, de luva, no tablet ou no celular, com pressa e com a balança do lado. O Renato e o Eduardo usam no computador. A tela tem que funcionar bem para o primeiro grupo; o segundo se adapta.

## 2. Princípios (valem para todas as telas)

1. **Uma tarefa por tela, um botão principal.** O botão principal é grande, azul, sempre no mesmo lugar (rodapé fixo no tablet/celular, fim do formulário no computador) e diz o que faz: "Confirmar corte", não "OK".
2. **O sistema preenche, o operador confere.** Campos [MEGA], [LOTE], [CALC] e [SISTEMA] aparecem como texto, não como campo editável. Só [DIGITADO] e [SUGERIDO] viram campo. [SUGERIDO] vem preenchido, com a marca "sugerido" ao lado.
3. **Pouca digitação.** Número abre teclado numérico (`inputMode="decimal"`), vírgula ou ponto aceitos, kg com 1 casa. Listas viram botões grandes quando têm até 4 opções (modo de corte, Sim/Não da bitola). OP é digitada uma vez e o resto aparece.
4. **Mostrar o resultado antes de gravar.** Toda ação que mexe em saldo mostra a frase do que vai acontecer ("Lote L-000451 passa de 1.288,0 kg para 0 kg…") logo acima do botão principal, como a especificação pede em T13.
5. **Validação em 3 cores, sempre igual** (componente `Ocorrencias`):
   - vermelho = bloqueia, botão principal desabilitado e a mensagem diz o que fazer;
   - amarelo (palha) = caixa "Estou ciente" + campo de justificativa (mínimo 10 caracteres, contador visível); botão só libera quando todos os amarelos estão resolvidos;
   - cinza = só aviso.
6. **Linguagem do chão, não do banco.** Nada de `SAIDA_CORTE_RJ` na tela: "Corte no RJ". Lote mostrado com contêiner e bitola junto ("L-000451 · CH25K · H13 70×610"). Números no formato brasileiro.
7. **Sem surpresa de saída.** Formulário com dado digitado avisa antes de sair da tela. Assistente (T07) guarda o passo em que está.
8. **Erro de rede não perde nada.** Se o envio falhar, os dados ficam na tela e aparece "Não gravou. Tente de novo." Nada de tela branca.

## 3. Dispositivo e tamanho

| Item | Regra |
|---|---|
| Alvo de toque | mínimo 48 px de altura em botões, campos e linhas clicáveis |
| Fonte | 16 px base; números de peso em destaque 24–48 px (Barlow Semi Condensed, algarismos tabulares) |
| Contraste | WCAG AA no mínimo; amarelo nunca é a única pista (sempre ícone + texto) |
| Tabelas no celular (< 900 px) | viram **cartões** empilhados com os 3–4 dados principais; o resto em "ver mais" |
| Rodapé de ação | fixo no celular/tablet com o botão principal e, no máximo, um secundário |
| Telas pensadas primeiro para tablet/celular | T09 Fila RJ, T10 Registrar corte, T12 Receber COP, T13 Corte em Itu, T20 Calculadora |
| Telas pensadas primeiro para computador | T04, T05, T14, T16, T19, T21–T25 (funcionam no tablet, sem prioridade de layout) |

## 4. Navegação

- Menu lateral **só com o que o perfil usa** (§4 da especificação). Itens sem permissão não aparecem; não ficam cinza.
- Grupos do menu iguais aos da especificação: Estoque, Barra Mansa, Itu, Controle, Administração.
- **Painel = "o que eu tenho para fazer agora"**: as pendências do perfil (T03) vêm primeiro, como cartões grandes com contador ("3 COPs para receber"). A barra de estoque fica abaixo.
- **Busca global** no topo de todas as telas (§4). Um resultado: abre direto. Mais de um (ex.: número que é OP e COP ao mesmo tempo): lista curta com o tipo de cada um.
- Sino de notificações no topo (§6); clicar no aviso abre o item.
- Toda lista abre o item em tela própria com endereço próprio (`/corte/123`), para poder mandar o link.

## 5. Componentes comuns (a construir em `frontend/src/components`)

| Componente | Uso |
|---|---|
| `Ocorrencias` (já existe) | ampliar com "Estou ciente" + justificativa para o nível CIENCIA |
| `CampoKg`, `CampoNumero` | teclado numérico, vírgula, 1 casa, unidade ao lado |
| `Escolha` | botões grandes para 2–4 opções (substitui select curto) |
| `Assistente` | passos numerados com "Voltar"/"Continuar" (T07) |
| `RodapeAcao` | barra fixa com botão principal + frase do resultado |
| `ResumoLote` | linha padrão: lote · contêiner · liga bitola · estoque (cor) · disponível |
| `Situacao` | etiqueta da situação do documento (§3) |
| `Prazo` | Normal / Atenção / Atrasado (7/15 dias, T03) com ícone + cor |
| `TabelaOuCartoes` | tabela no computador, cartões no celular |
| `CampoMega` | campo [MEGA] com estado "não confirmado no Mega" quando o Mega estiver fora (§7) |

Cores com significado fixo (já no `app.css`): azul = Estoque Mega, púrpura = RJ no Rio, bronze = RJ em Itu, palha = exige "estou ciente", vermelho = bloqueia.

## 6. Ordem proposta de construção

| Etapa | Telas | Depende de |
|---|---|---|
| F1.0 | Componentes comuns, menu por perfil, Painel com pendências, busca global (casca) | R009 |
| F1.1 | T04 Consulta de estoque, T05 Detalhe do lote | R010 (API de lotes) |
| F1.2 | T07 Nova solicitação (assistente), T08 Lista | R005, R010 (OP no Mega + validações) |
| F1.3 | T09 Fila RJ, T10 Registrar corte | R003, R004 |
| F1.4 | T11 COP, T12 Receber COP | R006 |
| F1.5 | T14 SA | — |
| F2 | T13 Corte em Itu, T15, T16, T17, T18 | R007, R008 |
| F3 | T06, T19, T22–T25 | R008 |

Enquanto a API de uma tela não existe, a tela é feita com dados de exemplo da própria especificação (OP 100592, 100092, 100553) atrás de uma chave de desenvolvimento, para o Eduardo e o Fabiano validarem o layout cedo.

## 7. Pendências que travam layout

Ver `coordenacao/PEDIDOS.md`: R003 (material insuficiente), R004 (encerrar parcial), R005 (modo "Cortar em Itu"), R006 (divergência/recebimento parcial), R007 (troca de OP), R008 (parâmetros faltantes), R009 (matriz perfil × tela), R010 (contrato da API, para o TÉCNICO).
