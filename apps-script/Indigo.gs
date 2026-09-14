const INDIGO_WORKFLOW = 'indigo-parking-search.yml';
const INDIGO_RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/indigo-parking-search.json';

function indigoValidTime_(value) {
  return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(String(value || ''));
}

function indigoDispatch_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${INDIGO_WORKFLOW}/dispatches`;
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    payload: JSON.stringify({
      ref: 'main',
      inputs: {
        entry_date: job.entry_date,
        exit_date: job.exit_date,
        exit_time: job.exit_time,
        from_time: job.from_time,
        to_time: job.to_time,
        step_minutes: String(job.step_minutes),
        product: job.product,
        request_id: job.job_id
      }
    }),
    headers: ghHeaders_()
  });
  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub recusou a pesquisa Indigo (' + response.getResponseCode() + '): ' + response.getContentText().slice(0, 500));
  }
}

function startIndigoSearch_(body) {
  const entryDate = String(body.entry_date || '').trim();
  const exitDate = String(body.exit_date || '').trim();
  const exitTime = String(body.exit_time || '07:00').trim();
  const fromTime = String(body.from_time || '05:00').trim();
  const toTime = String(body.to_time || '14:00').trim();
  const step = Number(body.step_minutes == null ? 30 : body.step_minutes);
  const product = String(body.product || 'terminal3_garage').trim();
  const requestedId = String(body.request_id || '').trim();

  if (!validDate_(entryDate) || !validDate_(exitDate)) throw new Error('Datas inválidas.');
  if (exitDate < entryDate) throw new Error('A data de saída precisa ser igual ou posterior à entrada.');
  if (!indigoValidTime_(exitTime) || !indigoValidTime_(fromTime) || !indigoValidTime_(toTime)) throw new Error('Horário inválido.');
  if (![15, 30, 60].includes(step)) throw new Error('Intervalo deve ser 15, 30 ou 60 minutos.');
  if (!['terminal3_garage','terminal3_flex','terminal2_standard','terminal1','any'].includes(product)) throw new Error('Produto Indigo inválido.');
  if (toTime < fromTime) throw new Error('O último horário precisa ser igual ou posterior ao primeiro.');

  const jobId = validJobId_(requestedId) ? requestedId : ('indigo_' + Utilities.getUuid().replace(/-/g, '').slice(0, 16));
  const job = {
    job_id: jobId,
    status: 'queued',
    entry_date: entryDate,
    exit_date: exitDate,
    exit_time: exitTime,
    from_time: fromTime,
    to_time: toTime,
    step_minutes: step,
    product: product,
    started_at: new Date().toISOString()
  };

  const props = PropertiesService.getScriptProperties();
  props.setProperty('INDIGO_JOB_' + jobId, JSON.stringify(job));
  indigoDispatch_(job);
  return { job_id: jobId, status: 'queued', cached: false };
}

function readIndigoResult_(job) {
  const response = UrlFetchApp.fetch(INDIGO_RESULT_RAW + '?t=' + Date.now(), {
    muteHttpExceptions: true,
    headers: { 'Cache-Control': 'no-cache' }
  });
  if (response.getResponseCode() !== 200) return null;
  try {
    const data = JSON.parse(response.getContentText());
    if (String(data.request_id || '') !== String(job.job_id)) return null;
    if (!data.request) return null;
    if (data.request.entry_date !== job.entry_date || data.request.exit_date !== job.exit_date) return null;
    if (String(data.request.exit_time || '') !== String(job.exit_time || '')) return null;
    if (String(data.request.from_time || '') !== String(job.from_time || '')) return null;
    if (String(data.request.to_time || '') !== String(job.to_time || '')) return null;
    if (Number(data.request.step_minutes) !== Number(job.step_minutes)) return null;
    if (String(data.request.product || '') !== String(job.product || '')) return null;
    return data;
  } catch (err) {
    return null;
  }
}

function readIndigoWorkflowStatus_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${INDIGO_WORKFLOW}/runs?event=workflow_dispatch&per_page=20`;
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: ghHeaders_() });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  const needle = 'Indigo ' + job.job_id + ' ·';
  const run = (data.workflow_runs || []).find(r => String(r.display_title || '').indexOf(needle) === 0);
  if (!run) return null;
  return { id: run.id, status: run.status, conclusion: run.conclusion, html_url: run.html_url };
}

function pollIndigoSearch_(jobId) {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('INDIGO_JOB_' + jobId);
  if (!raw) return { job_id: jobId, status: 'error', error: 'Pesquisa Indigo não encontrada ou expirada.' };
  const job = JSON.parse(raw);
  const ageMs = Date.now() - new Date(job.started_at).getTime();
  if (ageMs > 30 * 60 * 1000) {
    props.deleteProperty('INDIGO_JOB_' + jobId);
    return { job_id: jobId, status: 'error', error: 'A pesquisa Indigo excedeu 30 minutos.' };
  }

  const result = readIndigoResult_(job);
  if (result) return { job_id: jobId, status: 'done', result: result };

  const run = readIndigoWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    return { job_id: jobId, status: 'error', error: 'A busca Indigo terminou com erro: ' + run.conclusion };
  }
  return { job_id: jobId, status: run && run.status ? run.status : 'running' };
}
