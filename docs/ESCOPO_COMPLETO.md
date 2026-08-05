# Escopo completo — Flight Deals Local

## Objetivo

Criar um aplicativo privado, portátil e local para Windows capaz de pesquisar grandes volumes de combinações de voos e destacar as melhores oportunidades encontradas.

O sistema deve maximizar a chance de encontrar tarifas difíceis de perceber manualmente, combinando múltiplas origens, destinos, datas, durações e filtros. Ele não promete tarifas secretas, preços exclusivos nem resultados que nenhum outro usuário possa encontrar. A vantagem virá da automação, da abrangência da pesquisa e do histórico próprio.

## Privacidade

- Uso exclusivamente pessoal.
- Repositório privado.
- Aplicativo executado localmente.
- Banco de dados SQLite local.
- Sem servidor próprio obrigatório.
- Sem cadastro público.
- Sem compartilhamento de histórico.
- Internet usada apenas para consultar fontes de voos e abrir páginas de confirmação.

## Funções obrigatórias

### Pesquisa flexível

- ida e volta;
- somente ida;
- múltiplos aeroportos de origem;
- múltiplos aeroportos de destino;
- datas exatas;
- intervalo de ida;
- intervalo de volta;
- mínimo e máximo de noites;
- adultos, crianças e bebês;
- econômica, premium economy, executiva e primeira classe;
- moeda BRL, USD e EUR;
- pesquisa por preço máximo;
- voos diretos ou com limite de escalas;
- duração total máxima;
- horários mínimos e máximos de partida e chegada;
- companhias incluídas e excluídas;
- aeroportos alternativos;
- pesquisa em lote de todas as combinações válidas;
- limite configurável de requisições e pausa entre consultas.

### Estratégias para encontrar preços baixos

- comparar todos os pares de aeroportos selecionados;
- testar todas as combinações de datas compatíveis;
- testar durações diferentes dentro do intervalo definido;
- ordenar por menor preço total;
- ordenar por menor preço por passageiro;
- comparar ida e volta conjunta com trechos separados;
- detectar open-jaw quando tecnicamente disponível;
- detectar aeroportos alternativos próximos;
- destacar combinações fora das datas mais óbvias;
- registrar menor preço observado por rota e período;
- detectar novo recorde de menor preço;
- calcular média, mediana e percentis do histórico;
- classificar possível deal com base no histórico local;
- permitir preço-alvo manual;
- permitir comparação por companhia, horário, escalas e duração;
- abrir link de confirmação da tarifa na fonte original.

### Histórico e inteligência

- banco SQLite local;
- registro de cada pesquisa;
- registro de cada resultado;
- gráfico de evolução por rota e combinação de datas;
- menor preço histórico;
- média histórica;
- mediana;
- variação percentual;
- comparação com última consulta;
- classificação: excelente, muito bom, bom, normal e caro;
- favoritos;
- notas pessoais;
- marcação de tarifas expiradas;
- comparação entre pesquisas salvas;
- exclusão seletiva ou total do histórico.

### Resultados

- ranking geral;
- ranking por origem;
- ranking por destino;
- ranking por companhia;
- ranking por duração;
- filtros instantâneos;
- companhia aérea;
- aeroportos;
- datas;
- horários;
- escalas;
- duração total;
- preço total;
- preço por passageiro;
- moeda;
- fonte;
- link de confirmação;
- indicação de bagagem quando a fonte fornecer;
- exportação CSV;
- exportação Excel;
- impressão ou relatório PDF em etapa posterior.

### Operação

- modo pesquisa pontual;
- modo repetir pesquisa salva;
- modo monitoramento enquanto o aplicativo estiver aberto;
- intervalo configurável entre verificações;
- alerta local quando atingir preço-alvo;
- alerta local quando surgir novo menor preço;
- execução sem Docker;
- executável portátil para Windows;
- dados salvos na pasta do usuário;
- logs para diagnóstico;
- recuperação segura após falha.

## Fontes e motores

A arquitetura deve permitir mais de um motor de consulta. O primeiro motor será baseado em Google Flights por meio de biblioteca compatível. Outros motores só serão adicionados quando forem tecnicamente estáveis, legalmente utilizáveis e compatíveis com o aplicativo local.

A aplicação deve separar:

1. motor de consulta;
2. normalização de resultados;
3. banco de dados;
4. detecção de deals;
5. interface;
6. exportação;
7. compilação Windows.

## Limitações explícitas

- O sistema não garante o menor preço absoluto de toda a internet.
- O sistema não garante tarifas invisíveis ou exclusivas.
- O preço pode mudar antes da compra.
- Bagagem, impostos e regras tarifárias podem variar.
- A confirmação deve ser feita na companhia aérea ou fonte original.
- Consultas excessivas podem ser bloqueadas temporariamente pela fonte.
- Recursos dependentes de serviços pagos serão opcionais.
- Técnicas que violem termos de uso, burlem autenticação ou contornem bloqueios de forma indevida não serão incorporadas.

## Critério de sucesso

O projeto será considerado bem-sucedido quando conseguir pesquisar automaticamente centenas ou milhares de combinações válidas, armazenar os resultados, identificar quedas relevantes e mostrar rapidamente as opções mais baratas que seriam trabalhosas de encontrar manualmente.
