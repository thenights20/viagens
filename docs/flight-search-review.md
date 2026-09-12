# Revisão da busca de passagens — 12/09/2026

## Causa comprovada
O diagnóstico isolado reproduziu o erro em fast-flights 3.1.0, parser.py, linha 72:
`if payload[3][0] is None`. O próprio `payload[3]` era nulo.
A falha também apareceu nas amostras de outubro, novembro e dezembro; não significava ausência de voos.
[Traceback original](https://github.com/thenights20/viagens/actions/runs/34717429736).

## Correções
- Parser do projeto valida grupos preferidos/outros, preços e segmentos antes de acessar índices. Grupos vazios retornam ausência de resultado; formato desconhecido continua sendo erro identificável.
- Todas as combinações sem preço seguem para o fallback, inclusive rotas não regionais com cobertura primária acima de 18%.
- Worker Swoop transmite cada resultado por JSONL; o processo principal salva progresso durante o lote, incluindo intervalos sem novas conclusões. Uma repetição de transporte cobre falhas transitórias.
- Snapshots contêm `all_results`, preservando os preços além do top 100. A interface continua limitando a tabela, com ordenação sobre todos os resultados disponíveis.
- Histórico inválido causa erro explícito em vez de ser substituído por vazio. Removida a exclusão automática de pares antigos.
- Uma implementação atualiza a interface. Progresso calculado por etapa; resultados associados ao request_id exato, sem depender do relógio do navegador. Recarregar retoma o acompanhamento sem novo envio.
- Contrato ativo: POST no endereço /exec com `?route=api/search`, corpo text/plain; confirmação por progresso/Actions/live, nunca pela resposta opaca.
- Solicitação desconhecida retorna `unknown`, não uma fila fictícia.
- Links do calendário, cidades, filtros de origem/destino/mês, ordem por preço, buscas salvas e retorno à busca atual permanecem disponíveis.
- Mantido o código interno de intervalo para preservar compatibilidade ponta a ponta com a implantação existente. Testado 13–15, com exatamente três pares.
- Uma única inclusão do carregador no HTML.

## Arquivos principais
`flight_response.py`, `search_core.py`, `flight-month-search/search.py`,
`flight-month-search/swoop_batch_worker.py`, `apps-script/Code.gs`,
`docs/flight-explorer.js`, `docs/terabyte-live.js`, `docs/index.html`.

Removidos:
- `.github/workflows/hotfix-flight-ui-v044.yml`
- `scripts/hotfix_flight_button_v047.py`
- `scripts/hotfix_flight_ui_v045.py`
- `scripts/hotfix_flight_ui_v046.py`
- `scripts/hotfix_flight_ui_v048.py`
- `scripts/install_flight_enhancements.py`
- `scripts/tune_flight_progress.py`
- `docs/flight-explorer-enhancements.js`

Testes permanentes: `tests/flight-search.test.cjs`, `tests/test_flight_search.py`,
`tests/flight-browser.cjs` e workflow de testes sem permissão de escrita.
Os scripts `scripts/audit_flight_search.py` e `scripts/check_flight_range.py`
são verificações explícitas; não modificam código nem publicam dados de teste.

## Evidências
[Validação final](https://github.com/thenights20/viagens/actions/runs/34718282144):
7 testes Python, 14 testes JavaScript, Chromium e execução real completa do intervalo DOU–GRU 13–15/01/2027:
3/3 combinações com preço, menor R$ 981, sem erros; histórico de outros meses comparado e preservado em cópia isolada.

[Sete amostras reais](https://github.com/thenights20/viagens/actions/runs/34717976279):
- Outubro 13–15: R$ 1.469.
- Novembro 13–15: R$ 680.
- Dezembro 13–15: R$ 981.
- Janeiro 13–15: R$ 1.265.
- Janeiro 01–10, 01–12 e 02–09: R$ 627 em cada consulta.

Preços são observações desses horários e podem mudar. O menor de R$ 981 no intervalo de janeiro corresponde a uma das três combinações, não necessariamente 13–15.

Chromium verificou links, histórico de novembro durante janeiro, filtros, progresso 456/465 → 98% e 120/300 → 40%, envio único, cancelamento e retomada após recarregar. As chamadas externas no teste de interface são simuladas; as consultas Python acima são reais.

## Dados anteriores
Nenhum JSON de produção foi alterado pela correção ou pelos testes.
Antes da publicação: outubro 348 pares (mínimo R$ 1.114), novembro 413 (R$ 680),
dezembro 410 (R$ 732), janeiro 272 (R$ 522).
A [busca completa de janeiro já em andamento](https://github.com/thenights20/viagens/actions/runs/34717071594)
terminou normalmente durante a revisão, sem ser cancelada.
Referência de dezembro: [execução bem-sucedida](https://github.com/thenights20/viagens/actions/runs/34713922389).

O link do site e o ID da implantação Apps Script foram mantidos.
