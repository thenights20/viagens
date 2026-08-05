# Flight Deals Local

Aplicativo privado e local para pesquisar passagens aéreas em múltiplos aeroportos e intervalos de datas, registrar histórico e identificar possíveis deals.

## Objetivo

Reunir em uma única aplicação as funções úteis observadas em projetos como VFD, FlightClaw e Flight Finder, sem depender de servidor próprio e sem publicar dados pessoais.

## Escopo inicial

- pesquisa de ida e volta;
- múltiplas origens e destinos;
- intervalo de datas;
- quantidade mínima e máxima de noites;
- classes econômica, premium economy, executiva e primeira classe;
- histórico local em SQLite;
- comparação com média e menor preço já registrado;
- classificação preliminar de deal;
- exportação CSV;
- compilação automática para Windows com GitHub Actions.

## Privacidade

O programa roda localmente. O banco de dados, favoritos e histórico permanecem no computador do usuário. A conexão com a internet é usada apenas para consultar os resultados de voos.

## Estado

Versão inicial em desenvolvimento. A primeira fase prioriza estabilidade da pesquisa e do executável antes da inclusão de gráficos, alertas e filtros avançados.
