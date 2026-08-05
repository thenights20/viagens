# Limites de pesquisa e quantidade de resultados

## Princípio

O sistema não terá um limite fixo baixo de combinações, como 150. Ele poderá analisar quantas combinações forem necessárias para completar a pesquisa solicitada.

## Controle técnico

Para evitar travamentos, bloqueios e consultas inúteis, a pesquisa será executada em lotes adaptativos, com:

- remoção de combinações duplicadas;
- cache de consultas já realizadas;
- priorização das combinações mais promissoras;
- aprofundamento progressivo;
- pausa e retomada da pesquisa;
- controle de concorrência;
- registro de progresso;
- interrupção segura pelo usuário.

O sistema não deve encerrar uma pesquisa apenas porque atingiu um número arbitrário de combinações. Limites internos poderão existir somente para proteger estabilidade, memória, tempo de execução e a fonte consultada, sempre com retomada automática ou opção de continuar.

## Quantidade de resultados finais

O usuário poderá escolher:

- Top 5;
- Top 10;
- Top 20;
- Top 30;
- Top 50.

A quantidade escolhida controla apenas o que será exibido, não o tamanho da pesquisa realizada.

## Qualidade dos resultados

Os resultados finais serão diversificados e deduplicados. O ranking deverá preservar categorias úteis, como:

- menor preço absoluto;
- melhor custo-benefício;
- melhor voo direto;
- melhor open jaw/crossover;
- melhor combinação com bilhetes separados;
- melhor opção de baixo risco;
- maior economia em relação ao histórico;
- melhor opção por aeroporto ou estado alternativo.

Resultados praticamente iguais não ocuparão várias posições. O sistema agrupará opções semelhantes e manterá a melhor representante.

## Modos de profundidade

- Rápido: varredura inicial e poucos aprofundamentos;
- Equilibrado: padrão recomendado;
- Profundo: pesquisa ampla, mais lenta e com maior cobertura;
- Máximo: executa até esgotar as combinações válidas ou o usuário interromper.

O modo Máximo não significa consultas simultâneas ilimitadas. Ele significa ausência de limite arbitrário no total de combinações, mantendo processamento responsável e progressivo.
