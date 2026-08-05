# Rotas avançadas e combinações de bilhetes

O sistema deve pesquisar, comparar e classificar estratégias além da ida e volta tradicional.

## Seleção geográfica

- seleção manual de aeroportos;
- seleção por cidade;
- seleção por estado/província;
- seleção por país;
- grupos regionais e turísticos;
- aeroportos próximos sugeridos automaticamente;
- possibilidade de combinar seleção por estado com aeroportos específicos.

## Estratégias de rota

### Ida e volta tradicional
Mesmo aeroporto de origem e destino nos dois sentidos.

### Open jaw
Chegada por um aeroporto/cidade e retorno por outro.
Exemplo: GRU → MIA e MCO → GRU.

### Multi-city
Viagem com dois ou mais destinos, pesquisada como um único itinerário.
Exemplo: GRU → MIA → NYC → GRU.

### Crossover de aeroportos
Combinar aeroportos próximos ou diferentes na ida e na volta.
Exemplo: saída por GRU e retorno por VCP; chegada por MIA e retorno por FLL.

### Bilhetes separados
Comparar:
- ida e volta em um único bilhete;
- dois bilhetes de ida;
- companhias diferentes em cada trecho;
- combinação doméstico + internacional em reservas separadas.

### Voo de posicionamento
Pesquisar um voo barato até um grande hub e, separadamente, o trecho internacional.
Exemplo: CGR → GRU e GRU → MIA.

### Self-transfer
Combinar bilhetes independentes com conexão por conta do passageiro. O sistema deve exigir margem de segurança configurável, indicar necessidade de retirar e redespachar bagagem e destacar que não há proteção automática em caso de atraso.

### Stopover útil
Comparar conexões longas que permitam visitar uma cidade, desde que o custo final seja competitivo.

## Ranking e segurança

Cada combinação deve considerar:
- preço total real;
- preço por passageiro;
- bagagem incluída quando disponível;
- custo e tempo de deslocamento entre aeroportos;
- hotel necessário em conexão longa;
- risco de bilhetes separados;
- necessidade de imigração e novo check-in;
- duração total porta a porta;
- economia frente à melhor ida e volta tradicional.

Resultados arriscados não devem ser ocultados, mas precisam aparecer com aviso claro e nota de risco.

## Hidden city
Não será tratado como estratégia recomendada. Caso apareça em análise futura, deve ser apenas informativo, com alerta de que pode violar regras tarifárias da companhia, impedir despacho de bagagem e causar cancelamento de trechos subsequentes.

## Saída resumida
Mesmo que milhares de combinações sejam analisadas, mostrar apenas poucos resultados distintos:
- menor preço absoluto;
- melhor custo-benefício;
- melhor crossover/open jaw;
- melhor combinação de bilhetes separados;
- melhor voo direto;
- melhor alternativa de baixo risco.
