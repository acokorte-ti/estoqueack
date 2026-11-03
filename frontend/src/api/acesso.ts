import type { Perfil } from "./cliente";

/** Matriz perfil × tela (especificação §4.1). A API aplica a mesma regra; aqui serve para o menu e as rotas. */
export const ACESSO = {
  novaSolicitacao: ["ESTOQUE", "ADMIN"],               // T07
  solicitacoes: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "ADMIN"], // T08 (RJ e Análise só consultam)
  filaRj: ["OPERACAO_RJ", "ESTOQUE", "ADMIN"],          // T09 (Itu só consulta)
  registrarCorte: ["OPERACAO_RJ", "ADMIN"],            // T10
  sa: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "ADMIN"],   // T14
  corteItu: ["ESTOQUE", "ADMIN"],                      // T13
} satisfies Record<string, Perfil[]>;
