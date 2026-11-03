import type { Perfil } from "./cliente";

/** Matriz perfil × tela (especificação §4.1). A API aplica a mesma regra; aqui serve para o menu e as rotas. */
export const ACESSO = {
  novaSolicitacao: ["ESTOQUE", "ADMIN"],
  sa: ["ESTOQUE", "OPERACAO_RJ", "ANALISE", "ADMIN"],
  corteItu: ["ESTOQUE", "ADMIN"],
} satisfies Record<string, Perfil[]>;
