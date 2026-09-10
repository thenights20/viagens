# Monitor de preços — lojas oficiais v0.2.0

Monitor pessoal para localizar **preços anormalmente baixos** em produtos de maior valor. O painel recebe somente anúncios cuja origem oficial e preço passam pela verificação e pela revalidação.

## Fontes

- **Mercado Livre:** tenta a API oficial; se a pesquisa pública exigir autenticação, usa o navegador e aceita apenas lojas oficiais previamente verificadas, reconfirmando o vendedor no anúncio antes de publicar uma anomalia.
- **Shopee:** varre páginas exatas de lojas oficiais verificadas e prende cada produto ao `shop_id` daquela loja. Recomendações de outros vendedores são descartadas.
- **Casas Bahia:** pesquisa o site e só aceita o item depois que a PDP confirma que é vendido pela própria Casas Bahia.

O sistema não contorna CAPTCHA, login ou proteções anti-bot. Se uma fonte impedir a leitura, ela falha de forma fechada e não produz falso positivo.

## Detector

Preferência de referência: mediana de pelo menos 3 ofertas equivalentes, depois mediana histórica de pelo menos 5 amostras. No primeiro ciclo, `preço de` só pode gerar alerta em uma diferença extrema. Padrão: referência >= R$ 2.000, economia >= R$ 1.000 e preço atual <= 55% da referência. Quando só existe `preço de`, exige referência >= R$ 3.000, economia >= R$ 2.000 e preço atual <= 35%.

Depois da detecção, o anúncio é aberto novamente. Só entra em `active` quando continua disponível, oficial e com o mesmo preço.

## Execução

Os runners públicos do GitHub foram testados e os três e-commerces limitaram a coleta. Por isso a automação v0.2.0 usa um **GitHub Actions self-hosted runner no Windows**: o código e o agendamento ficam no GitHub, enquanto a consulta usa sua conexão normal. Veja `RUNNER_WINDOWS.md`.

Execução manual local:

```powershell
$env:PYTHONPATH="price-monitor/src"
python -m pip install -r price-monitor/requirements.txt
python -m pytest -q price-monitor/tests
python -m price_monitor.run --config price-monitor/config.json --output price-monitor/site/data/current.json --history price-monitor/data/history.json
```
