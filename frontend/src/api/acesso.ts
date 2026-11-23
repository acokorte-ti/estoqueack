import type { Perfil } from "./cliente";

/** Matriz perfil × tela (especificação §4.1). A API aplica a mesma regra; aqui serve para o menu e as rotas.
 *  Financeiro (spec v3.21, a Bruna): grava só o R$/kg do precificador no Cadastro de SA e consulta o resto. */
export const ACESSO = {
  estoque: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "FINANCEIRO", "ADMIN"], // T04/T05 (RJ só RJ no Rio, a API filtra)
  entradaNf: ["OPERACAO_RJ", "ESTOQUE", "ANALISE", "FINANCEIRO", "ADMIN"], // T06 (só RJ e Admin lançam)
  novaSolicitacao: ["ESTOQUE", "ADMIN"],                        // T07
  solicitacoes: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "FINANCEIRO", "ADMIN"], // T08 (RJ, Análise e Financeiro só consultam)
  filaRj: ["OPERACAO_RJ", "ESTOQUE", "ADMIN"],                  // T09 (Itu só consulta)
  registrarCorte: ["OPERACAO_RJ", "ADMIN"],                     // T10
  cop: ["OPERACAO_RJ", "ESTOQUE", "ANALISE", "FINANCEIRO", "ADMIN"], // T11 (Itu, Análise e Financeiro consultam)
  receberCop: ["ESTOQUE", "OPERACAO_RJ", "ADMIN"],              // T12 (RJ consulta)
  corteItu: ["ESTOQUE", "ADMIN"],                               // T13
  sa: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "FINANCEIRO", "ADMIN"], // T14 (Financeiro: R$/kg)
  entradasMega: ["ESTOQUE", "ANALISE", "ADMIN"],                // T15 (Estoque Itu e Admin alteram; Análise só vê; RJ não vê)
  conciliacao: ["ESTOQUE", "ANALISE", "ADMIN"],                 // T16 mínima (só leitura)
} satisfies Record<string, Perfil[]>;
