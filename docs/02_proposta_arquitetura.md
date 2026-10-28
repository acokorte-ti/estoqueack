# Controle de Matéria-Prima AçoKorte — Proposta de Arquitetura e Solução

Versão 1 para validação, 28/10/2026. Base: `01_Analise_Processo_Atual.md` e as respostas do Eduardo às 12 perguntas.

---

## 1. Decisões já tomadas

| # | Tema | Decisão |
|---|---|---|
| 1 | ERP Mega | Não há API, mas existe acesso ao banco de dados. A integração será por consultas SQL (ver §4). |
| 2 | Hospedagem | VM própria na Oracle Cloud ou na AWS, publicada no domínio da empresa. A empresa tem Microsoft 365. |
| 3 | Pessoas | Marcelo (RJ) opera corte, liberação e COP. Fabiano Camargo (Itu) faz todas as movimentações, e Matheus Almeida é o substituto dele. Renato Pinto visualiza, analisa e comenta sobre compras. |
| 3 | Aprovação | Não haverá aprovação humana. Toda ação passa por **validação automática antecipada** contra o estoque. |
| 4 | COP | Controle de Ordem de Produção: o pacote que o Marcelo fecha ao carregar o caminhão para Itu. Fio Certo, Médio Vale e Renafer são tratados como "RJ". |
| 5 | Contêiner | É o lote de importação, usado só como ID. Corrida e certificado ficam fora por enquanto. |
| 6 | ESTOQUE 2026 | Cobre todo o material fiscal RJ, tanto no Rio quanto em Itu. |
| 7 | Peso | **Tudo é pesado.** A fórmula serve só para a **previsão** do peso de uma peça que ainda vai ser cortada (para a NF). |
| 8 | Granularidade | Controle por kg por lote. Controle por peça e etiqueta fica para uma fase futura. |
| 9 | RETO Mega | O material Mega cortado em Itu **também** gera RETO com rastreabilidade de origem. |
| 10 | Destinação | Destinação e restrição viram regra do sistema. Na baixa, o usuário precisa confirmar "estou ciente". |
| 11 | Perda de corte | Não é registrada como movimento, mas entra na **tolerância** das validações de peso (corte de 2 a 3 mm). |
| 12 | Histórico | Todo o histórico existente será importado. |
| 13 | Banco do Mega | Oracle 19c numa VM da OCI. O Eduardo é administrador e cria um usuário somente leitura. |
| 14 | MP prevista na OP | Existe no Mega, mas não é confiável. Vale o que foi **baixado de fato**. O sistema mostra a MP prevista só como informação e não valida contra ela. |
| 15 | Entrada RJ | O Marcelo registra a entrada de material no RJ a partir da NF. |
| 16 | Valor R$/kg | Fora do foco inicial. O foco é **peso**. O campo de valor existe, mas é opcional. |
| 17 | Endereço e código | `estoque.acokorte.com.br`. Repositório: `github.com/acokorte-ti/estoqueack`. |
| 18 | Escrita no Mega | Por enquanto só consulta. A arquitetura já deixa um ponto preparado para atualizar o Mega pelo sistema no futuro. |
| 19 | Hospedagem | **Opção A: OCI Always Free (Ampere A1)**, tanto para homologação quanto para produção. |
| 20 | Tolerância | **Revisada em 28/10:** o peso previsto já inclui o sobremetal, então o excedente aceito é de até **5 %**. Acima disso, o sistema alerta e obriga o operador a justificar o uso a mais de matéria-prima. |
| 21 | Login | **Usuários e senhas no banco do próprio sistema**, sem Microsoft 365. |

---

## 2. Arquitetura geral

```
            Usuários (Itu e RJ) – navegador, celular ou tablet
                         │  HTTPS + login Microsoft 365 (SSO + MFA)
                         ▼
   ┌──────────────────────── VM na nuvem (AWS ou OCI) ────────────────────────┐
   │  Caddy (proxy reverso, certificado HTTPS automático, rate-limit)          │
   │      ├── Front-end web (React + TypeScript)                               │
   │      └── API REST (Python FastAPI)  ── OpenAPI documentada                │
   │              ├── Regras de negócio + validações                           │
   │              ├── Worker de tarefas (sincronização Mega, e-mails, backup)  │
   │              └── PostgreSQL 16 (banco do sistema)                         │
   └──────────────────────────────────┬───────────────────────────────────────┘
                                      │ túnel seguro (somente saída, a partir de Itu)
                                      ▼
                    Conector Mega (serviço leve numa máquina em Itu)
                                      │ SQL somente leitura
                                      ▼
                             Banco de dados do ERP Mega
```

**Por que esse desenho:**

- **O sistema tem banco próprio (PostgreSQL)** e não grava nada no banco do Mega. O Mega continua sendo a referência fiscal. O sistema é a referência de rastreabilidade por lote.
- **O Conector Mega fica em Itu, ao lado do banco do ERP,** e só faz conexões de saída. Nenhuma porta do ERP fica exposta na internet.
- **Tudo roda em containers Docker**, com o mesmo pacote nos ambientes de homologação e produção. Isso facilita reinstalar, migrar de nuvem ou subir um servidor local se um dia for preciso.
- **A API REST com OpenAPI** atende o site e permite integrações futuras, como um app de leitor, Power BI ou o próprio Mega.

### 2.1 Tecnologias

| Camada | Tecnologia | Motivo |
|---|---|---|
| Front-end | React 18 + TypeScript + Vite, biblioteca de componentes (Mantine ou MUI) | Interface rápida e responsiva, com tipagem que evita erro |
| Back-end | Python 3.12 + FastAPI + SQLAlchemy 2 + Pydantic | Validação forte de dados e ótimo suporte a Oracle e SQL Server, o que ajuda no acesso ao Mega |
| Banco | PostgreSQL 16 | Transações ACID, integridade referencial e consultas recursivas para a árvore de origem dos lotes |
| Migrações de banco | Alembic | Versiona cada mudança de estrutura |
| Autenticação | Microsoft Entra ID (o login do 365), OIDC + MFA | Sem senha nova. Quem sai da empresa perde o acesso na hora |
| Tarefas agendadas | APScheduler ou Celery + Redis | Sincronização com o Mega, alertas e relatórios |
| Proxy e HTTPS | Caddy | HTTPS automático (Let's Encrypt) |
| Testes | pytest (back-end), Vitest e Playwright (front-end) | As regras de estoque precisam ter testes automatizados |
| Integração e entrega contínuas (CI/CD) | GitHub Actions | Testes e deploy automáticos e rastreáveis |
| Monitoramento | Uptime Kuma + logs estruturados + Sentry (plano gratuito) | Aviso de queda e de erro antes que o usuário reclame |

---

## 3. Hospedagem: opções e custos

Valores **aproximados**, em dólar por mês, de acordo com as tabelas públicas que conheço. É preciso confirmar no painel de cada provedor antes de contratar.

| Opção | O que inclui | Custo/mês | Prós | Contras |
|---|---|---|---|---|
| **A. OCI Always Free** (Ampere A1, até 4 vCPU / 24 GB, 200 GB de disco) | VM única com tudo em Docker | **US$ 0** | Grátis e com folga de hardware | Sem SLA. A Oracle pode recuperar instâncias ociosas. Arriscado para produção |
| **B. VM paga única** (AWS Lightsail 4 GB ou EC2 t4g.medium, ou VM paga na OCI) + backup externo | App + PostgreSQL + Caddy na mesma VM, com snapshot diário e dump em object storage | **≈ US$ 25–45** | Simples, barato e suficiente para dezenas de usuários | O banco divide a máquina com a aplicação |
| **C. VM + banco gerenciado** (EC2 + RDS PostgreSQL, ou OCI + PostgreSQL gerenciado) | Backup automático com restauração em qualquer instante (point-in-time) | **≈ US$ 70–120** | Mais resiliente e com menos manutenção | Custa mais |

Itens comuns às três opções: domínio (vocês já têm, ex.: `estoque.acokorte.com.br`), certificado HTTPS (grátis), túnel seguro do conector (Cloudflare Tunnel ou Tailscale, plano gratuito, ou VPN IPSec da OCI, também gratuita) e o login Microsoft (já incluso no 365).

**Recomendação:** usar a **Opção A para homologação** e a **Opção B para produção**, com backup diário criptografado fora da VM e teste de restauração mensal. Se o volume ou a criticidade crescerem, a migração para a Opção C é direta, porque tudo já está em Docker.

---

## 4. Integração com o ERP Mega

### 4.1 Leitura (recomendada desde o início)

Haverá um usuário de banco **somente leitura**, criado pelo TI ou pelo DBA. O conector consulta:

- os **saldos físicos e o preço médio** dos códigos de MP (o que hoje vem do relatório "Inventário C.M.D."), com frequência diária ou sob demanda, e não mais semanal;
- as **OPs**: número, item, cliente, situação e, se existir, a MP prevista na estrutura;
- o **cadastro de itens**: código, descrição, UM e NCM;
- os **SA cadastrados**, para confirmar automaticamente que o SA solicitado foi criado e ler o código gerado.

Com isso, `historicos_pcp.xlsx`, a aba "estoque atual" colada e a aba "Quant consider" deixam de existir.

### 4.2 Escrita no Mega: recomendo **não** gravar direto nas tabelas

Um INSERT ou UPDATE direto no banco de um ERP pula as regras fiscais, os gatilhos e a numeração interna. Isso pode corromper dados fiscais e normalmente faz o fornecedor recusar suporte. A proposta é esta:

1. O sistema **monta o pedido de cadastro de SA já preenchido e validado** (descrição, NCM, ICMS, IPI, peso, valor, origem), pronto para copiar ou exportar.
2. A pessoa cadastra o SA no Mega, como já faz hoje.
3. O conector **lê o SA criado** e fecha o vínculo automaticamente. Se não achar o SA em X horas, o sistema avisa.
4. Se o Mega tiver uma ferramenta oficial de importação ou integração, é possível automatizar o passo 2 numa fase futura, sem risco.

---

## 5. Conceito do modelo: Lote, Movimento e Árvore de origem

Os números do exemplo abaixo são ilustrativos.

```
Contêiner CH11EA
 └─ Lote L-000123  H13 50×610  (RJ fiscal, físico RJ)  peso inicial 5.004 kg
      ├─ movimento: Corte p/ OP 100092 – 837 kg (cortado no RJ, COP 598)
      ├─ movimento: Transferência física RJ→Itu (peça inteira) 1.288 kg ──► Lote L-000451 (RJ fiscal, físico Itu)
      │                                                                     ├─ Consumo OP 100359 – 1.111 kg
      │                                                                     └─ Sobra fora de bitola 177 kg ──► Lote L-000452  H13 RETO (origem: L-000123 / 50×610 / CH11EA)
      └─ saldo atual: calculado = soma dos movimentos
```

Regras do modelo:

- **Os movimentos não se apagam.** Para corrigir, faz-se um estorno vinculado ao original. É isso que garante a auditoria.
- **O saldo de cada lote é calculado** a partir dos movimentos e conferido por restrições do banco: o saldo nunca fica negativo.
- **O RETO é um lote filho** que sempre aponta para o pai. O relatório "kg de H13 RETO por bitola e contêiner de origem" sai de uma consulta recursiva.
- **Os três estoques** (Mega, RJ no Rio e RJ em Itu) são **filtros** (planta fiscal × local físico), e não colunas digitadas.
- **No estoque Mega**, o sistema mantém o detalhamento por lote, e o Mega mantém o saldo fiscal por código. Uma tela de conciliação mostra, por código, a diferença entre a soma dos lotes e o saldo do Mega.

---

## 6. Banco de dados (principais tabelas)

| Tabela | Campos-chave |
|---|---|
| `liga` | código (H13, D2, A8, CR12MoV…), nomes alternativos (1.2344, DIN 1.2344…), **densidade g/cm³** |
| `item_mp` | código Mega (pode ser nulo para itens só do RJ), liga, formato (chapa/barra retangular, redondo, RETO), espessura, largura, diâmetro, comprimento fixado, UM, observação de uso |
| `conteiner` | código (CH11EA…), data de entrada, planta fiscal, observação |
| `lote` | id, contêiner, item_mp, planta fiscal (ITU/RJ), local físico (ITU/RJ), tipo (ORIGINAL/SOBRA/RETO), **lote_pai_id**, peso inicial, quantidade inicial de peças, custo R$/kg, status |
| `movimento` | id, tipo (ENTRADA, RESERVA, CORTE_RJ, ENVIO_ITU, RECEBIMENTO, CONSUMO_OP, SOBRA, TRANSF_RETO, AJUSTE, ESTORNO), lote, kg (+/−), peças, OP, SA, COP, solicitação, usuário, data/hora, justificativa |
| `ordem_producao` | cópia lida do Mega: número, item, cliente, situação |
| `solicitacao_corte` | OP, item, medida acabada, quantidade, lote escolhido, modo (CORTAR_NO_RJ / TRAZER_INTEIRA), peso previsto, instrução de corte, prazo, **status** |
| `liberacao_corte` | solicitação, peças cortadas, **peso real**, data |
| `cop` | número, data de fechamento, itens (liberações), status (aberto, fechado, em trânsito, recebido) |
| `cadastro_sa` | solicitação/OP, código SA no Mega, descrição, NCM, ICMS, IPI, peso, quantidade, valor, NF de transferência, status (pendente, confirmado no Mega) |
| `destinacao` | lote, destino (produto, cliente ou item), tipo (RESERVA / RESTRIÇÃO "não usar para…"), kg, validade, autor |
| `nota` | comentários do Renato e de outros (compras futuras, análises) em lote, item ou liga |
| `usuario`, `perfil` | vínculo com a conta Microsoft |
| `auditoria` | quem, quando, o quê, valor antes/depois (JSON), IP |
| `sync_mega` | registro de cada sincronização: horário, registros lidos e erros |

---

## 7. Fluxos e validações automáticas

Toda ação passa pelas validações **antes** de ser gravada. Erro bloqueia a ação. Alerta pede confirmação explícita ("estou ciente"), e essa confirmação fica registrada na auditoria.

### 7.1 Solicitação de corte RJ (Fabiano ou Matheus)

1. O usuário digita a OP. O sistema busca o item, a medida e o cliente no Mega.
2. O sistema **sugere lotes compatíveis**: liga correta, bitola maior ou igual à medida acabada mais o sobremetal, e saldo disponível.
3. O usuário escolhe o modo **Cortar no RJ** ou **Trazer peça inteira**.
4. O peso previsto é calculado pela densidade da liga e já fica disponível para a NF.

Validações:

- **Erro** se a OP não existir ou estiver encerrada.
- **Erro** se o peso previsto for maior que o saldo disponível do lote (saldo menos reservas).
- **Alerta** se a bitola for menor que a medida acabada.
- **Alerta** se o lote tiver destinação ou restrição.
- **Alerta** se já existir solicitação ou SA para a mesma OP.

### 7.2 Corte e liberação no RJ (Marcelo)

O Marcelo vê a fila de solicitações por prazo, com a mesma regra de status de hoje (Normal, Atenção, Atrasado), e registra as peças cortadas e o **peso real**.

Validações:

- **Erro** se o peso real for maior que o saldo do lote.
- **Alerta** se o peso real for diferente do previsto além da tolerância.
- **Alerta** se forem cortadas mais peças do que o solicitado.

### 7.3 COP (Marcelo)

O Marcelo monta o pacote com as liberações prontas, fecha o COP e imprime ou envia o romaneio. Itens que não estão liberados não entram.

### 7.4 Recebimento em Itu (Fabiano ou Matheus)

O usuário confere o COP item a item. O que chega pesado é confirmado, e as peças inteiras viram um lote **RJ fiscal / físico Itu**.

### 7.5 Cadastro de SA (Fabiano ou Matheus)

O sistema gera o pedido de SA já preenchido. Ele faz o mesmo cálculo de valor que existe hoje (R$/kg × peso ÷ quantidade) e preenche origem = contêiner e lote.

- **Erro** se o peso do SA for maior que o peso liberado ou consumido.
- **Erro** se o SA for duplicado para a mesma OP e o mesmo lote.

Depois, o conector confirma o código do SA no Mega.

### 7.6 Corte em Itu, sobra e RETO (vale para Mega e para RJ em Itu)

O usuário informa o consumo da OP e a **sobra pesada**. O sistema pergunta se a sobra **ainda está na bitola original**:

- **Se sim**, a sobra continua no mesmo lote, só como saldo.
- **Se não**, o sistema cria um lote **RETO filho** com a origem herdada automaticamente.

Validação:

- **Alerta** se a perda (peso antes − consumo − sobra) passar da tolerância de corte.

### 7.7 Destinação e restrição

Renato, Fabiano ou Matheus marcam um lote como reservado, ou como "não usar para guilhotinas". Toda baixa nesse lote exige o aceite.

### 7.8 Ajuste de inventário

O ajuste exige justificativa obrigatória e é destacado nos relatórios.

### 7.9-A Regra de tolerância de 5 % (decisão 20, revisada)

O peso previsto já é calculado **com sobremetal**. Por isso, o excedente aceito é pequeno: o parâmetro `TOLERANCIA_EXCESSO_PCT` vale **5 %** e é configurável.

- **Peso real até 5 % acima do previsto:** grava normalmente.
- **Peso real mais de 5 % acima do previsto:** o sistema alerta, mostra quantos kg a mais estão sendo usados e **só grava com justificativa** (mínimo de 10 caracteres). Exemplo: previsto 100 kg, real 106 kg, então o operador precisa justificar os 6 kg a mais.
- **Peso real mais de 20 % abaixo do previsto:** alerta simples, porque provavelmente é erro de pesagem ou digitação.
- **Na solicitação**, a relação entre bitola e peça acabada aparece só como informação (sobremetal alto), sem bloquear.

Toda justificativa fica registrada (quem, quando, quanto a mais e por quê) e aparece no painel "Exceções de tolerância" do administrador.

### 7.9 Tolerância de peso por perda de corte

A perda de um corte é calculada como **espessura da serra (2 a 3 mm) × área da seção × densidade**. Exemplo: um corte transversal em 35×610 com serra de 3 mm perde 35 × 610 × 3 mm³ × 7,85 g/cm³ ≈ **0,50 kg**. O sistema calcula essa perda esperada e só alerta quando a diferença passa dela, mais uma margem que vocês poderão configurar.

### 7.10 Densidade (resposta à pergunta 7)

O mais correto é usar **densidade por liga**, e não um número único. A fórmula atual usa 7,85, e a nota da planilha diz 7,9. Valores de referência da literatura técnica (a confirmar com os fornecedores): H13/1.2344 ≈ 7,80; D2/Cr12MoV/D6 ≈ 7,70; A8 ≈ 7,85; O1 ≈ 7,85; 4140 ≈ 7,85; padrão para ligas não cadastradas = 7,85. Os valores ficam editáveis na tela de administração. Como tudo é pesado depois, a densidade só influencia a **previsão** para a NF e os alertas.

---

## 8. Telas

| # | Tela | Quem usa | Função |
|---|---|---|---|
| 1 | Login Microsoft | Todos | SSO + MFA |
| 2 | **Painel** | Todos | Saldos dos três estoques, cortes atrasados, COPs em trânsito, SAs pendentes de confirmação, divergências com o Mega e "minhas pendências" |
| 3 | **Consulta de estoque** | Todos | Busca por liga, bitola, contêiner ou código Mega, com filtro por estoque. Visão de lista e agrupada |
| 4 | **Detalhe do lote** | Todos | Saldo, histórico de movimentos, árvore de origem e filhos (RETO), destinações e notas |
| 5 | Entrada de lote / contêiner | Fabiano, Matheus | Cadastro de material novo (RJ ou Mega) |
| 6 | **Nova solicitação de corte** | Fabiano, Matheus | Assistente: OP → lote sugerido → modo → peso previsto → validações |
| 7 | **Fila RJ** | Marcelo | Solicitações por prazo e registro do corte e do peso real |
| 8 | **COP** | Marcelo | Montar, fechar e imprimir o pacote |
| 9 | Recebimento em Itu | Fabiano, Matheus | Check por COP |
| 10 | **Cadastro de SA** | Fabiano, Matheus | Pedido pré-preenchido, exportação e status de confirmação no Mega |
| 11 | **Consumo / corte em Itu** | Fabiano, Matheus | Baixa por OP, sobra e geração de RETO |
| 12 | Destinações e restrições | Renato, Fabiano, Matheus | Reservas e bloqueios |
| 13 | Conciliação Mega | Fabiano, Matheus, Renato | Lotes × saldo do ERP por código |
| 14 | **Relatórios** | Todos | RETO por origem, consumo por OP, cliente e período, valor em estoque, giro, histórico. Exporta para Excel |
| 15 | Calculadora de peso | Todos | Reto, redondo e anel, com densidade por liga |
| 16 | Administração | Admin | Usuários e perfis, catálogo de ligas e itens, densidades, tolerâncias, auditoria |

As telas serão responsivas, para o Marcelo usar no tablet ou no celular no chão de fábrica.

---

## 9. Perfis e permissões

| Ação | Admin | Estoque Itu (Fabiano, Matheus) | Operação RJ (Marcelo) | Análise (Renato) |
|---|:-:|:-:|:-:|:-:|
| Consultar estoque e relatórios | ✔ | ✔ | ✔ | ✔ |
| Solicitar corte / trazer peça | ✔ | ✔ | – | – |
| Registrar corte, peso real e COP | ✔ | – | ✔ | – |
| Receber em Itu, SA, consumo, RETO | ✔ | ✔ | – | – |
| Destinação e restrição | ✔ | ✔ | – | ✔ |
| Notas e comentários | ✔ | ✔ | ✔ | ✔ |
| Ajuste de inventário | ✔ | ✔ (com justificativa) | – | – |
| Administração | ✔ | – | – | – |

---

## 10. Segurança

- **Login exclusivo pelo Microsoft 365**, com MFA. Os perfis são atribuídos no sistema, com mínimo privilégio.
- **HTTPS obrigatório.** O banco de dados não fica exposto na internet, e o firewall libera só as portas 80 e 443.
- O conector Mega usa um **usuário somente leitura** e um túnel apenas de saída.
- **Auditoria completa**, com antes e depois de cada alteração. Os movimentos são imutáveis.
- **Senhas e chaves ficam fora do código**, em variáveis protegidas ou num gerenciador de segredos.
- **Backup diário criptografado, guardado fora da VM**, com retenção de 30 dias, cópias mensais por 12 meses e teste de restauração periódico.
- Atualizações de segurança automáticas no sistema operacional, imagens Docker com versão fixa e análise de dependências na esteira de CI/CD.
- Validação de entrada no servidor (Pydantic), proteção contra os riscos do OWASP Top 10 e rate limiting.

---

## 11. Migração do histórico

1. **Catálogo mestre:** unificar os nomes de ligas e bitolas (CR12MOV, CR12 MOV, Cr12MoV etc.) a partir das quatro planilhas, e revisar com o Fabiano os casos duvidosos.
2. **ESTOQUE 2026 e HISTORICO:** cada linha vira um lote (contêiner + bitola) com a entrada original. Cada célula de consumo vira um movimento, e **a OP e a data são extraídas dos comentários**.
3. **SA de 2016 a 2025** (incluindo os dados de 2026 que estão na aba 2025) e **Controle de Corte**: importação como histórico vinculado por OP e contêiner.
4. **Estoque Geral:** os saldos de RJ em Itu e de RETO **que hoje não têm origem** entram como lotes "origem não identificada", separados por liga. Recomendo um **inventário físico inicial** para atribuir origem onde for possível. Daqui em diante, toda sobra nasce rastreada.
5. **Saldos Mega:** carga inicial pela leitura do ERP.
6. **Reconciliação:** um relatório compara os totais do sistema com as planilhas antes da virada, e as diferenças são revisadas uma a uma.

---

## 12. Plano de entregas sugerido

| Fase | Entrega |
|---|---|
| 0 – Fundação | Infraestrutura, login Microsoft, catálogo de ligas e itens, banco, CI/CD, homologação no ar |
| 1 – Estoque RJ | Lotes, consulta, solicitação de corte, fila RJ, COP, recebimento, SA e migração do histórico RJ |
| 2 – Itu e RETO | Consumo em Itu, sobra e RETO rastreado, destinações e restrições |
| 3 – Mega | Conector de leitura, OPs automáticas, confirmação de SA e conciliação |
| 4 – Relatórios | Painéis, rastreabilidade de RETO e exportações |
| Futuro | Controle por peça com etiqueta e QR Code, leitor de inventário, corrida e certificado |

---

## 12-A. Ajustes da v2 (prevalecem sobre as seções anteriores)

- **Autenticação local:** senhas guardadas com hash **Argon2id**. A sessão fica no servidor, num cookie `HttpOnly; Secure; SameSite=Strict`, com token CSRF. A conta é bloqueada por 15 minutos após 5 tentativas erradas. A senha precisa ter pelo menos 10 caracteres, a troca é obrigatória no primeiro acesso e o administrador pode redefinir senhas. Todo login, falha e logout fica na auditoria. Um segundo fator (TOTP) pode ser ativado no futuro.
- **Hospedagem:** OCI Always Free, numa VM ARM64. Recomendações: (a) mudar a conta OCI para *Pay As You Go*, o que mantém os recursos grátis e evita que a Oracle recupere instâncias ociosas; (b) fazer backup diário no Object Storage da OCI (20 GB grátis) **e** uma cópia fora da OCI.
- **Conector Mega:** como o Oracle 19c também está na OCI, o sistema pode acessá-lo **pela rede privada da OCI** (mesma VCN ou peering), liberando a porta 1521 só para a VM do sistema. Nesse caso, o túnel deixa de ser necessário. O acesso usa o driver `python-oracledb` em modo *thin*, sem precisar instalar o Oracle Client. A interface `MegaGateway` tem leitura implementada, e a escrita fica preparada para o futuro, mas desabilitada.
- **Planilhas e dados reais não vão para o GitHub.** O repositório tem só código e documentação. A migração lê as planilhas a partir de uma pasta local fora do repositório.

## 13. Pontos que ainda dependem de resposta

Estão na conversa. Depois das respostas, esta proposta vira a especificação final e começamos a Fase 0.
