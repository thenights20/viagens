# Flight Deals Local v0.5.0

Aplicativo privado e local para Windows que pesquisa combinações de passagens, organiza os preços e preserva alternativas de datas no banco SQLite.

## Novidades da v0.5.0

- modo **Turbo adaptativo** com até três consultas simultâneas;
- redução automática da velocidade quando a fonte apresenta muitas falhas;
- retomada gradual do modo Turbo quando a fonte volta a ficar estável;
- períodos de 30 dias, 3 meses, 6 meses e 12 meses;
- intervalo personalizado de datas;
- seletor visual de meses específicos dentro dos próximos 24 meses;
- banco de preços com uma linha para cada combinação de rota, ida e volta;
- aba **Melhor preço por rota**;
- aba **Preços por datas**, ordenada do menor para o maior;
- exibição dos 100, 500, 2.000 ou de todos os preços salvos;
- exportação das alternativas de datas para CSV.

## Recursos preservados

- pesquisa de ida e volta em até 365 dias;
- 91 aeroportos brasileiros cadastrados;
- modos Rápido, Equilibrado, Profundo e Máximo;
- Profundo e Máximo verificam todos os dias e todas as estadias do intervalo informado;
- execução local enquanto o aplicativo permanece aberto ou minimizado;
- prevenção de suspensão do Windows durante a pesquisa;
- salvamento contínuo do progresso;
- pausa, retomada e cancelamento seguro;
- cache local de seis horas;
- histórico e identificação de novo recorde;
- previsão aproximada do tempo restante;
- duplo clique para conferir a tarifa no Google Flights.

## Como usar

1. Baixe o artefato `Flight-Deals-Local-Windows-v0.5.0` na execução mais recente do GitHub Actions.
2. Extraia o ZIP e execute `Flight Deals Local.exe`.
3. Informe origens e destinos ou use **Brasil inteiro**.
4. Escolha um período pronto, um intervalo ou meses específicos.
5. Defina as noites mínima e máxima.
6. Para cobertura completa, selecione **Profundo**. Para maior velocidade, selecione **Turbo adaptativo (3)**.
7. Clique em **Iniciar pesquisa**.

O modo Turbo não usa VPN, rotação de IP ou técnicas de evasão. Se a fonte começar a falhar, o próprio aplicativo reduz a concorrência.

## Banco de preços

Os resultados ficam em:

`%USERPROFILE%\FlightDealsLocal\flight_deals.db`

Cada pesquisa mantém:

- o vencedor absoluto de cada rota;
- o menor preço encontrado para cada combinação exata de rota e datas;
- progresso, quantidade de erros e configurações necessárias para retomada.

## Fonte inicial e limitações

A versão 0.5.0 consulta o Google Flights por meio da biblioteca `fast-flights`. A fonte reúne diversas companhias, mas não garante cobertura absoluta de todas as empresas ou tarifas. Preços, bagagem e regras podem mudar antes da compra. O computador e o aplicativo precisam permanecer ligados durante a execução.

