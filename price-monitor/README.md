# Ferramenta pessoal de acompanhamento

Módulo de uso pessoal para acompanhar ofertas públicas em diferentes varejistas e organizar os resultados em uma página simples.

O projeto prioriza fontes identificáveis e, em marketplaces, considera apenas lojas oficiais previamente configuradas. Os resultados são conferidos novamente antes de aparecerem na página principal.

## Fontes

A configuração atual reúne marketplaces conhecidos e varejistas com operação própria. Novas fontes podem ser adicionadas em `config.json` sem alterar a lógica principal.

## Execução

A automação usa um GitHub Actions self-hosted runner no Windows. O código e o agendamento ficam no GitHub, enquanto a consulta usa a conexão normal do computador.

Veja `RUNNER_WINDOWS.md` para a configuração inicial.

Execução manual local:

```powershell
$env:PYTHONPATH="price-monitor/src"
python -m pip install -r price-monitor/requirements.txt
python -m pytest -q price-monitor/tests
python -m price_monitor.run --config price-monitor/config.json --output price-monitor/site/data/current.json --history price-monitor/data/history.json
```

Projeto pessoal, sem vínculo comercial com as lojas ou plataformas consultadas.
