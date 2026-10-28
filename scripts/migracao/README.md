# Migração das planilhas (Fase 1)

As planilhas **não** ficam no repositório. Coloque-as numa pasta local, por exemplo `../dados/`, e aponte o script para ela.

Etapas previstas:

1. **Catálogo:** extrair ligas e bitolas de todas as planilhas com `app.domain.medidas.interpretar` e gerar uma planilha de revisão para o Fabiano.
2. **ESTOQUE 2026 e HISTORICO:** criar um lote por linha (contêiner + bitola). Cada célula de consumo vira um movimento, com OP e data extraídas do **comentário da célula**.
3. **SA de 2016 a 2025** (incluindo os dados de 2026 da aba 2025) e **Controle de Corte RJ**: importar como histórico vinculado por OP e contêiner.
4. **Estoque Geral:** os saldos de RJ em Itu e de RETO sem origem viram lotes `origem_identificada = false`.
5. **Conferência:** um relatório compara os totais por estoque com as planilhas antes da virada.
