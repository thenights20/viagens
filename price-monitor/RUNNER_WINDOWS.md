# Coletor no Windows com GitHub Actions

## Por que self-hosted

Os testes em 10/09/2026 mostraram que os IPs dos runners públicos do GitHub são recusados ou recebem páginas diferentes em Mercado Livre, Shopee e Casas Bahia. O código continua no GitHub e o agendamento continua no GitHub Actions, mas a navegação usa a conexão normal do seu Windows. Não há bypass de CAPTCHA ou proteção anti-bot.

## Configuração única

1. No repositório, abra **Settings > Actions > Runners > New self-hosted runner**.
2. Escolha **Windows / x64**.
3. Execute no PowerShell os comandos que o próprio GitHub mostrar. Eles contêm um token temporário exclusivo da sua conta; não salve esse token no repositório.
4. Quando o GitHub perguntar pelo nome, pode usar `price-monitor`.
5. Instale o runner como serviço quando a opção for oferecida, para ele iniciar com o Windows.
6. Confirme que Chrome ou Microsoft Edge está instalado.

Quando o runner aparecer como **Idle/Online**, o workflow `Monitor de preços oficiais` pode ser executado manualmente e também roda de hora em hora, no minuto 17.

## Segurança

O coletor aceita somente fontes configuradas como oficiais. Mercado Livre tenta a API oficial e cai para navegador se a busca pública exigir autenticação. Shopee vincula cada produto ao `shop_id` dominante da loja oficial previamente verificada. Casas Bahia só aceita o produto depois que a página do produto confirma `Vendido por Casas Bahia` (ou equivalente). Em qualquer dúvida, o item é descartado.
