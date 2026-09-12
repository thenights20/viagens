const OWNER = 'thenights20';
const REPO = 'viagens';
const WORKFLOW = 'flight-month-search.yml';
const RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/flight-month-search.json';

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function githubToken_() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('GITHUB_TOKEN não configurado nas propriedades do script.');
  return token;
}

function dispatchSearch_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    payload: JSON.stringify({
      ref: 'main',
      inputs: {
        origin: job.origin,
        destination: job.destination,
        month: job.month,
        max_stops: String(job.max_stops),
        request_id: job.job_id
      }
    }),
    headers: {
      Authorization: 'Bearer ' + githubToken_(),
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    }
  });
  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub recusou a pesquisa (' + response.getResponseCode() + '): ' + response.getContentText().slice(0, 500));
  }
}

function startSearch_(body) {
  const origin = String(body.origin || '').trim().toUpperCase();
  const destination = String(body.destination || '').trim().toUpperCase();
  const month = String(body.month || '').trim();
  const maxStops = Number(body.max_stops == null ? 2 : body.max_stops);

  if (!/^[A-Z]{3}$/.test(origin) || !/^[A-Z]{3}$/.test(destination)) throw new Error('Origem/destino inválidos.');
  if (origin === destination) throw new Error('Origem e destino não podem ser iguais.');
  if (!/^20\d\d-(0[1-9]|1[0-2])$/.test(month)) throw new Error('Mês inválido.');
  if (![0, 1, 2].includes(maxStops)) throw new Error('Escalas inválidas.');

  const jobId = Utilities.getUuid().replace(/-/g, '').slice(0, 16);
  const job = {
    job_id: jobId,
    status: 'queued',
    origin: origin,
    destination: destination,
    month: month,
    max_stops: maxStops,
    started_at: new Date().toISOString()
  };

  PropertiesService.getScriptProperties().setProperty('JOB_' + jobId, JSON.stringify(job));
  try {
    dispatchSearch_(job);
  } catch (err) {
    PropertiesService.getScriptProperties().deleteProperty('JOB_' + jobId);
    throw err;
  }
  return { job_id: jobId, status: 'queued', cached: false };
}

function readResult_(job) {
  const response = UrlFetchApp.fetch(RESULT_RAW + '?t=' + Date.now(), {
    muteHttpExceptions: true,
    headers: { 'Cache-Control': 'no-cache' }
  });
  if (response.getResponseCode() !== 200) return null;
  try {
    const data = JSON.parse(response.getContentText());
    if (String(data.request_id || '') !== String(job.job_id)) return null;
    if (!data.request) return null;
    if (data.request.origin !== job.origin || data.request.destination !== job.destination || data.request.month !== job.month) return null;
    return data;
  } catch (err) {
    return null;
  }
}

function readWorkflowStatus_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=10`;
  const response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + githubToken_(),
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    }
  });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  const needle = 'Busca ' + job.job_id + ' ·';
  const run = (data.workflow_runs || []).find(r => String(r.display_title || '').indexOf(needle) === 0);
  if (!run) return null;
  return { status: run.status, conclusion: run.conclusion, html_url: run.html_url };
}

function pollSearch_(jobId) {
  const key = 'JOB_' + jobId;
  const raw = PropertiesService.getScriptProperties().getProperty(key);
  if (!raw) return { job_id: jobId, status: 'error', error: 'Pesquisa não encontrada ou expirada.' };

  const job = JSON.parse(raw);
  const ageMs = Date.now() - new Date(job.started_at).getTime();
  if (ageMs > 45 * 60 * 1000) {
    PropertiesService.getScriptProperties().deleteProperty(key);
    return { job_id: jobId, status: 'error', error: 'A pesquisa excedeu 45 minutos.' };
  }

  const result = readResult_(job);
  if (result) {
    PropertiesService.getScriptProperties().deleteProperty(key);
    return { job_id: jobId, status: 'done', result: result };
  }

  const run = readWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    PropertiesService.getScriptProperties().deleteProperty(key);
    return { job_id: jobId, status: 'error', error: 'A busca terminou com erro no servidor: ' + run.conclusion };
  }

  return { job_id: jobId, status: run && run.status ? run.status : 'running' };
}

function doPost(e) {
  try {
    const path = String((e && e.pathInfo) || '').replace(/^\/+|\/+$/g, '');
    if (path !== 'api/search') return json_({ error: 'Rota inválida.' });
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    return json_(startSearch_(body));
  } catch (err) {
    return json_({ error: String(err && err.message ? err.message : err) });
  }
}

function doGet(e) {
  try {
    const path = String((e && e.pathInfo) || '').replace(/^\/+|\/+$/g, '');
    if (!path || path === 'health') return json_({ ok: true, service: 'flight-search-bridge' });
    const match = path.match(/^api\/search\/([a-f0-9]{16})$/i);
    if (!match) return json_({ error: 'Rota inválida.' });
    return json_(pollSearch_(match[1]));
  } catch (err) {
    return json_({ error: String(err && err.message ? err.message : err), status: 'error' });
  }
}
