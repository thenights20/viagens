# Pesquisa por mês flexível

## Objetivo

Permitir que o usuário selecione um ou mais meses para ida e um ou mais meses para volta, sem obrigar uma duração fixa de viagem.

Exemplo:

- Ida: janeiro ou fevereiro de 2027
- Volta: janeiro ou fevereiro de 2027
- Duração: livre

O sistema deve analisar todas as combinações válidas em que a volta seja posterior à ida.

## Modos de duração

1. Livre: qualquer quantidade de dias entre ida e volta.
2. Intervalo opcional: mínimo e máximo de noites.
3. Faixas prontas: fim de semana, 4 a 7 noites, 7 a 14 noites, 15 a 30 noites, longa permanência.

No modo livre, o sistema não deve exigir permanência mínima ou máxima, mas pode aplicar limites técnicos configuráveis para evitar combinações absurdas ou consultas excessivas.

## Seleção de período

A interface deve aceitar:

- mês completo;
- vários meses;
- ano e mês;
- intervalo contínuo entre duas datas;
- dias da semana preferidos ou excluídos;
- datas bloqueadas;
- feriados opcionais.

## Estratégia de busca

Uma pesquisa ampla não deve consultar todas as combinações de forma ingênua quando o volume for muito alto.

Etapas:

1. gerar todas as combinações teoricamente válidas;
2. eliminar volta anterior ou igual à ida;
3. agrupar por rota e duração;
4. fazer varredura inicial por datas promissoras;
5. aprofundar somente as melhores faixas;
6. deduplicar resultados semelhantes;
7. exibir apenas Top 5, Top 10 ou Top 20.

## Ranking final

O sistema deve destacar:

- menor preço absoluto;
- melhor custo-benefício;
- melhor voo direto;
- melhor open jaw/crossover;
- melhor combinação com bilhetes separados;
- menor preço por duração curta, média e longa;
- novo menor preço histórico.

## Segurança e transparência

Cada resultado deve informar claramente:

- datas exatas;
- quantidade de noites;
- aeroportos de ida e volta;
- preço total e por passageiro;
- escalas;
- duração total;
- se há bilhetes separados;
- riscos de conexão própria;
- data e hora da coleta.
