import type { Perfil } from "./cliente";

/** Matriz perfil × tela (especificação §4.1). A API aplica a mesma regra; aqui serve para o menu e as rotas. */
export const ACESSO = {
  estoque: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "ADMIN"],      // T04/T05 (RJ só RJ no Rio, a API filtra)
  entradaNf: ["OPERACAO_RJ", "ESTOQUE", "ANALISE", "ADMIN"],    // T06 (só RJ e Admin lançam)
  novaSolicitacao: ["ESTOQUE", "ADMIN"],                        // T07
  solicitacoes: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "ADMIN"], // T08 (RJ e Análise só consultam)
  filaRj: ["OPERACAO_RJ", "ESTOQUE", "ADMIN"],                  // T09 (Itu só consulta)
  registrarCorte: ["OPERACAO_RJ", "ADMIN"],                     // T10
  cop: ["OPERACAO_RJ", "ESTOQUE", "ANALISE", "ADMIN"],          // T11 (Itu e Análise consultam)
  receberCop: ["ESTOQUE", "OPERACAO_RJ", "ADMIN"],              // T12 (RJ consulta)
  corteItu: ["ESTOQUE", "ADMIN"],                               // T13
  sa: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "ADMIN"],           // T14
} satisfies Record<string, Perfil[]>;
