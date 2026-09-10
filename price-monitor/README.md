# Monitor de preços — lojas oficiais

Monitor pessoal para localizar **preços anormalmente baixos** em produtos de maior valor, exibindo somente anúncios cuja loja oficial e preço continuam ativos na revalidação.

## Fontes iniciais

- Mercado Livre: API de busca, aceitando somente resultados com identificação de loja oficial.
- Shopee: varredura de páginas de lojas oficiais previamente configuradas, com nova checagem do anúncio quando há anomalia.
- Casas Bahia: busca pelo site e aceitação somente quando a página do produto confirma que é vendido pela própria Casas Bahia.

O sistema **não tenta contornar CAPTCHA, login, bloqueios ou proteções anti-bot**. Se uma fonte bloquear a leitura, ela é marcada como indisponível e nenhum anúncio não verificado entra no painel.

## Como decide se algo é anormal

A referência preferencial é:
1. mediana de pelo menos 3 ofertas oficiais equivalentes no momento;
2. mediana histórica de pelo menos 5 amostras;
3. apenas no primeiro ciclo, preço anterior anunciado — usado somente para diferenças extremas.

Padrão:
- referência >= R$ 2.000;
- economia >= R$ 1.000;
- preço atual <= 55% da referência;
- quando só existe “preço de”, exige referência >= R$ 3.000, economia >= R$ 2.000 e preço atual <= 35%.

Depois de detectar, o anúncio é aberto novamente. **Só entra em `active` se continuar disponível, oficial e com o mesmo preço.**

## Execução local

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r price-monitor/requirements.txt
PYTHONPATH=price-monitor/src python -m price_monitor.run \
  --config price-monitor/config.json \
  --output price-monitor/site/data/current.json \
  --history price-monitor/data/history.json
```

Para testar só a API do Mercado Livre, acrescente `--skip-browser`.

## Automação

`.github/workflows/price-monitor.yml` executa a varredura de hora em hora e também pode ser acionado manualmente. Instala Python e Chrome, roda testes, coleta, salva histórico/resultado e tenta publicar `price-monitor/site` no GitHub Pages se Pages estiver habilitado.
