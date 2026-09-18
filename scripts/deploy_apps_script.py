"""Update the existing Apps Script deployment without changing its public URL."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://script.googleapis.com/v1'


def credentials(raw):
    config = json.loads(raw)
    candidates = [config, config.get('token', {})]
    candidates.extend(config.get('tokens', {}).values())
    for candidate in candidates:
        if isinstance(candidate, dict) and all(candidate.get(k) for k in ('client_id', 'client_secret', 'refresh_token')):
            return {k: candidate[k] for k in ('client_id', 'client_secret', 'refresh_token')}
    raise RuntimeError('CLASPRC_JSON não contém uma autorização completa. Execute clasp login e atualize o segredo.')


def request(url, method='GET', payload=None, token=None, form=False):
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = None
    if payload is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        body = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never print OAuth responses, request headers or the secret.
        if 'oauth2.googleapis.com' in url:
            raise RuntimeError(f'Autorização Google recusada (HTTP {exc.code}). Execute clasp login novamente e atualize CLASPRC_JSON.') from None
        raise RuntimeError(f'Apps Script API recusou {method} (HTTP {exc.code}). Confira acesso ao projeto e habilitação da Apps Script API.') from None


def deploy(call, project, deployment_id, source):
    base = f'{API}/projects/{project}'
    deployment = call(f'{base}/deployments/{deployment_id}')
    config = deployment['deploymentConfig']
    if config.get('scriptId', project) != project:
        raise RuntimeError('A implantação não pertence ao projeto informado.')
    content = call(base + '/content')
    files = content['files']
    if not any(f.get('name') == 'appsscript' and f.get('type') == 'JSON' for f in files):
        raise RuntimeError('Manifesto remoto ausente; publicação interrompida.')
    candidates = [f for f in files if f.get('type') == 'SERVER_JS' and re.search(r'function\s+startSearch_\s*\(', f.get('source', '')) and re.search(r'function\s+dispatchSearch_\s*\(', f.get('source', ''))]
    if len(candidates) != 1:
        raise RuntimeError('Não foi possível identificar um único arquivo do serviço de pesquisa.')
    target_name = candidates[0]['name']
    updated = []
    replaced = False
    for remote in files:
        file = {k: remote[k] for k in ('name', 'type', 'source') if k in remote}
        if file['name'] == target_name and file['type'] == 'SERVER_JS':
            file['source'] = source
            replaced = True
        updated.append(file)
    if not replaced:
        raise RuntimeError('Arquivo Code.gs não encontrado no projeto; publicação interrompida para evitar duplicação.')
    call(base + '/content', method='PUT', payload={'files': updated})
    version = call(base + '/versions', method='POST', payload={'description': 'GitHub: flight bridge ' + os.environ.get('GITHUB_SHA', '')[:12]})
    new_config = {k: config[k] for k in ('scriptId', 'manifestFileName', 'description') if k in config}
    new_config['versionNumber'] = version['versionNumber']
    call(f'{base}/deployments/{deployment_id}', method='PUT', payload={'deploymentConfig': new_config})
    print(f"Implantação existente atualizada para versão {version['versionNumber']}. URL preservada.")


def main():
    raw = os.environ.pop('CLASPRC_JSON', '')
    if not raw:
        raise RuntimeError('Cadastre o segredo CLASPRC_JSON em Settings > Secrets and variables > Actions.')
    auth = credentials(raw)
    auth['grant_type'] = 'refresh_token'
    token = request('https://oauth2.googleapis.com/token', 'POST', auth, form=True)['access_token']
    def call(url, **kwargs):
        return request(url, token=token, **kwargs)
    server_files = sorted(Path('apps-script').glob('*.gs'))
    if not server_files:
        raise RuntimeError('Nenhum arquivo .gs encontrado para publicação.')
    source = '\n\n'.join(path.read_text(encoding='utf-8') for path in server_files)
    deploy(call, os.environ['SCRIPT_ID'], os.environ['DEPLOYMENT_ID'], source)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc) if isinstance(exc, RuntimeError) else f'Falha na implantação: {type(exc).__name__}', file=sys.stderr)
        sys.exit(1)
