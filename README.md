# Flight Deals Local v0.4.0

Aplicativo privado e local para Windows que pesquisa muitas combinações de passagens e conserva somente o menor preço encontrado para cada rota.

## Novidades da v0.4.0

- pesquisa de ida e volta em até 365 dias;
- botão **Brasil inteiro** para origens e destinos;
- modos Rápido, Equilibrado, Profundo e Máximo;
- os modos Profundo e Máximo verificam todos os dias do período;
- pesquisa executada em segundo plano enquanto o aplicativo permanece aberto ou minimizado;
- prevenção de suspensão do Windows durante a pesquisa;
- salvamento do progresso após cada consulta;
- botões para pausar, continuar e cancelar com segurança;
- retomada depois de fechar ou reiniciar o computador;
- cache local de seis horas para evitar repetição desnecessária;
- somente um resultado por rota: o menor preço encontrado;
- histórico local e identificação de novo recorde de preço;
- previsão aproximada do tempo restante;
- exportação dos vencedores para CSV;
- duplo clique para conferir o preço no Google Flights.

## Como usar

1. Baixe o artefato `Flight-Deals-Local-Windows-v0.4.0` na execução mais recente do GitHub Actions.
2. Extraia o arquivo ZIP.
3. Execute `Flight Deals Local.exe`.
4. Informe uma ou mais origens por código IATA ou selecione estados.
5. Informe os destinos ou use **Brasil inteiro**.
6. Escolha o período, a quantidade de noites e a profundidade.
7. Clique em **Iniciar pesquisa**.

Pesquisas com centenas de milhares de consultas podem levar dias. O aplicativo salva o avanço continuamente; use **Pausar** antes de desligar o computador e **Continuar última** ao abrir novamente.

## Onde os dados ficam

O histórico e o progresso são armazenados em:

`%USERPROFILE%\FlightDealsLocal\flight_deals.db`

Nenhum servidor próprio é necessário. A internet é usada somente para consultar preços e abrir a página de confirmação.

## Fonte inicial

A versão 0.4.0 usa o Google Flights por meio da biblioteca `fast-flights`. Essa fonte normalmente reúne voos de diversas companhias, mas não garante cobertura absoluta de todas as tarifas ou empresas. O preço precisa ser confirmado antes da compra.

## Limitações

- preços podem mudar rapidamente;
- bagagem e regras tarifárias podem variar;
- consultas excessivas podem sofrer bloqueio temporário;
- o programa não burla autenticação, CAPTCHA ou bloqueios dos sites;
- o computador e o aplicativo precisam permanecer ligados durante a execução;
- fechar o programa interrompe o processamento, mas o ponto salvo pode ser retomado.

