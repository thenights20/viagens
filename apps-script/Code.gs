const OWNER = 'thenights20';
const REPO = 'viagens';
const WORKFLOW = 'flight-month-search.yml';
const RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/flight-month-search.json';

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function jsonp_(obj, callback) {
  const cb = String(callback || '').trim();
  if (!/^[A-Za-z_$][A-Za-z0-9_$.]{0,120}$/.test(cb)) return json_(obj);
  return ContentService.createTextOutput(cb + '(' + JSON.stringify(obj) + ');').setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function githubToken_() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('GITHUB_TOKEN não configurado nas propriedades do script.');
  return token;
}

function ghHeaders_() {
  return {
    Authorization: 'Bearer ' + githubToken_(),
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function validJobId_(value) {
  return /^[A-Za-z0-9_-]{8,80}$/.test(String(value || ''));
}

function setProgress_(jobId, patch) {
  const props = PropertiesService.getScriptProperties();
  const key = 'PROGRESS_' + jobId;
  let current = {};
  try { current = JSON.parse(props.getProperty(key) || '{}'); } catch (err) {}
  const next = Object.assign({}, current, patch || {}, {
    request_id: jobId,
    updated_at: new Date().toISOString()
  });
  props.setProperty(key, JSON.stringify(next));
  return next;
}

function getProgress_(jobId) {
  const raw = PropertiesService.getScriptProperties().getProperty('PROGRESS_' + jobId);
  if (!raw) return { request_id: jobId, status: 'queued', stage: 'queued', percent: 1, message: 'Aguardando início da execução.' };
  try { return JSON.parse(raw); } catch (err) { return { request_id: jobId, status: 'running', stage: 'starting', percent: 2 }; }
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
    headers: ghHeaders_()
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
  const requestedId = String(body.request_id || '').trim();

  if (!/^[A-Z]{3}$/.test(origin) || !/^[A-Z]{3}$/.test(destination)) throw new Error('Origem/destino inválidos.');
  if (origin === destination) throw new Error('Origem e destino não podem ser iguais.');
  if (!/^20\d\d-(0[1-9]|1[0-2])$/.test(month)) throw new Error('Mês inválido.');
  if (![0, 1, 2].includes(maxStops)) throw new Error('Escalas inválidas.');

  const jobId = validJobId_(requestedId) ? requestedId : Utilities.getUuid().replace(/-/g, '').slice(0, 16);
  const job = {
    job_id: jobId,
    status: 'queued',
    origin: origin,
    destination: destination,
    month: month,
    max_stops: maxStops,
    started_at: new Date().toISOString()
  };

  const props = PropertiesService.getScriptProperties();
  props.setProperty('JOB_' + jobId, JSON.stringify(job));
  setProgress_(jobId, { status: 'queued', stage: 'queued', percent: 1, completed: 0, priced: 0, message: 'Pesquisa recebida. Aguardando GitHub Actions.' });
  try {
    dispatchSearch_(job);
  } catch (err) {
    props.deleteProperty('JOB_' + jobId);
    setProgress_(jobId, { status: 'error', stage: 'error', percent: 0, error: String(err.message || err) });
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
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=20`;
  const response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: ghHeaders_()
  });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  const needle = 'Busca ' + job.job_id + ' ·';
  const run = (data.workflow_runs || []).find(r => String(r.display_title || '').indexOf(needle) === 0);
  if (!run) return null;
  return { id: run.id, status: run.status, conclusion: run.conclusion, html_url: run.html_url };
}

function progressUpdate_(body) {
  const jobId = String(body.request_id || '').trim();
  if (!validJobId_(jobId)) throw new Error('request_id inválido.');
  const allowed = ['status','stage','percent','total','completed','remaining','priced','current_pair','fallback_done','fallback_total','message','error'];
  const patch = {};
  allowed.forEach(k => { if (body[k] !== undefined) patch[k] = body[k]; });
  return setProgress_(jobId, patch);
}

function cancelSearch_(body) {
  const jobId = String(body.request_id || '').trim();
  if (!validJobId_(jobId)) throw new Error('request_id inválido.');
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('JOB_' + jobId);
  if (!raw) {
    setProgress_(jobId, { status: 'canceled', stage: 'canceled', message: 'Pesquisa cancelada ou já finalizada.' });
    return { ok: true, status: 'canceled', request_id: jobId };
  }
  const job = JSON.parse(raw);
  setProgress_(jobId, { status: 'canceling', stage: 'canceling', message: 'Solicitando cancelamento ao GitHub Actions.' });

  let run = null;
  for (let i = 0; i < 8 && !run; i++) {
    run = readWorkflowStatus_(job);
    if (!run) Utilities.sleep(800);
  }
  if (!run) {
    job.status = 'cancel_requested';
    props.setProperty('JOB_' + jobId, JSON.stringify(job));
    return { ok: true, status: 'canceling', request_id: jobId, message: 'Execução ainda não apareceu no GitHub; cancelamento marcado.' };
  }
  if (run.status === 'completed') {
    const status = run.conclusion === 'success' ? 'done' : 'canceled';
    setProgress_(jobId, { status: status, stage: status, percent: status === 'done' ? 100 : undefined });
    return { ok: true, status: status, request_id: jobId };
  }

  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/runs/${run.id}/cancel`;
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    headers: ghHeaders_()
  });
  const code = response.getResponseCode();
  if (![202, 409].includes(code)) throw new Error('GitHub recusou o cancelamento (' + code + ').');
  job.status = 'cancel_requested';
  props.setProperty('JOB_' + jobId, JSON.stringify(job));
  setProgress_(jobId, { status: 'canceled', stage: 'canceled', message: 'Execução cancelada pelo usuário.' });
  return { ok: true, status: 'canceled', request_id: jobId };
}

function pollSearch_(jobId) {
  const key = 'JOB_' + jobId;
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty(key);
  if (!raw) return { job_id: jobId, status: 'error', error: 'Pesquisa não encontrada ou expirada.' };

  const job = JSON.parse(raw);
  if (job.status === 'cancel_requested') return { job_id: jobId, status: 'canceled' };
  const ageMs = Date.now() - new Date(job.started_at).getTime();
  if (ageMs > 45 * 60 * 1000) {
    props.deleteProperty(key);
    return { job_id: jobId, status: 'error', error: 'A pesquisa excedeu 45 minutos.' };
  }

  const result = readResult_(job);
  if (result) {
    setProgress_(jobId, { status: 'done', stage: 'done', percent: 100, completed: result.stats && result.stats.combinations, total: result.stats && result.stats.combinations, priced: result.stats && result.stats.priced_combinations });
    return { job_id: jobId, status: 'done', result: result };
  }

  const run = readWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    const canceled = run.conclusion === 'cancelled';
    setProgress_(jobId, { status: canceled ? 'canceled' : 'error', stage: canceled ? 'canceled' : 'error', error: canceled ? undefined : 'A busca terminou com erro no servidor: ' + run.conclusion });
    return { job_id: jobId, status: canceled ? 'canceled' : 'error', error: canceled ? undefined : 'A busca terminou com erro no servidor: ' + run.conclusion };
  }

  return { job_id: jobId, status: run && run.status ? run.status : 'running' };
}

function doPost(e) {
  try {
    const path = String((e && e.parameter && e.parameter.route) || (e && e.pathInfo) || '').replace(/^\/+|\/+$/g, '');
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (path === 'api/search') return json_(startSearch_(body));
    if (path === 'api/progress') return json_(progressUpdate_(body));
    if (path === 'api/cancel') return json_(cancelSearch_(body));
    return json_({ error: 'Rota inválida.' });
  } catch (err) {
    return json_({ error: String(err && err.message ? err.message : err), status: 'error' });
  }
}

function doGet(e) {
  try {
    const path = String((e && e.parameter && e.parameter.route) || (e && e.pathInfo) || '').replace(/^\/+|\/+$/g, '');
    if (!path || path === 'health') return json_({ ok: true, service: 'flight-search-bridge', version: '0.3.1' });
    let match = path.match(/^api\/progress\/([A-Za-z0-9_-]{8,80})$/);
    if (match) return jsonp_(getProgress_(match[1]), e && e.parameter && e.parameter.callback);
    match = path.match(/^api\/search\/([A-Za-z0-9_-]{8,80})$/);
    if (match) return json_(pollSearch_(match[1]));
    return json_({ error: 'Rota inválida.' });
  } catch (err) {
    return json_({ error: String(err && err.message ? err.message : err), status: 'error' });
  }
}
