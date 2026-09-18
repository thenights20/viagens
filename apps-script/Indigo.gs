const INDIGO_WORKFLOW = 'indigo-parking-search.yml';
const INDIGO_CHECKPOINT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/indigo-live/docs/data/indigo-checkpoints/';

function indigoValidTime_(value) {
  return /^(?:[01]\d|2[0-3]):(?:00|30)$/.test(String(value || ''));
}

function indigoMinutes_(value) {
  const p = String(value || '').split(':').map(Number);
  return p[0] * 60 + p[1];
}

function indigoDateValues_(fromDate, toDate) {
  const result = [];
  const end = new Date(toDate + 'T12:00:00Z');
  for (let cursor = new Date(fromDate + 'T12:00:00Z'); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    result.push(cursor.toISOString().slice(0, 10));
  }
  return result;
}

function indigoTimeValues_(fromTime, toTime) {
  const result = [];
  for (let value = indigoMinutes_(fromTime); value <= indigoMinutes_(toTime); value += 30) {
    result.push(String(Math.floor(value / 60)).padStart(2, '0') + ':' + String(value % 60).padStart(2, '0'));
  }
  return result;
}

function indigoCombinationCount_(entryDateFrom, entryDateTo, entryFromTime, entryToTime, exitDateFrom, exitDateTo, exitFromTime, exitToTime) {
  const entries = [];
  const exits = [];
  indigoDateValues_(entryDateFrom, entryDateTo).forEach(function(date) {
    indigoTimeValues_(entryFromTime, entryToTime).forEach(function(time) { entries.push(Date.parse(date + 'T' + time + ':00Z')); });
  });
  indigoDateValues_(exitDateFrom, exitDateTo).forEach(function(date) {
    indigoTimeValues_(exitFromTime, exitToTime).forEach(function(time) { exits.push(Date.parse(date + 'T' + time + ':00Z')); });
  });
  exits.sort(function(a, b) { return a - b; });
  let total = 0;
  entries.forEach(function(entry) {
    let low = 0;
    let high = exits.length;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (exits[middle] <= entry) low = middle + 1;
      else high = middle;
    }
    total += exits.length - low;
  });
  return total;
}

function indigoSearchKey_(job) {
  const canonical = [
    'v3', job.entry_date_from, job.entry_date_to, job.entry_from_time, job.entry_to_time,
    job.exit_date_from, job.exit_date_to, job.exit_from_time, job.exit_to_time, '30', job.product
  ].join('|');
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, canonical, Utilities.Charset.UTF_8)
    .map(function(value) { return ('0' + ((value + 256) % 256).toString(16)).slice(-2); }).join('');
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
        entry_date_from: job.entry_date_from,
        entry_date_to: job.entry_date_to,
        exit_date_from: job.exit_date_from,
        exit_date_to: job.exit_date_to,
        entry_from_time: job.entry_from_time,
        entry_to_time: job.entry_to_time,
        exit_from_time: job.exit_from_time,
        exit_to_time: job.exit_to_time,
        step_minutes: '30',
        product: job.product,
        request_id: job.job_id,
        search_key: job.search_key
      }
    }),
    headers: ghHeaders_()
  });
  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub recusou a pesquisa Indigo (' + response.getResponseCode() + '): ' + response.getContentText().slice(0, 500));
  }
}

function startIndigoSearch_(body) {
  const entryDateFrom = String(body.entry_date_from || body.entry_date || '').trim();
  const entryDateTo = String(body.entry_date_to || body.entry_date || entryDateFrom).trim();
  const exitDateFrom = String(body.exit_date_from || body.exit_date || '').trim();
  const exitDateTo = String(body.exit_date_to || body.exit_date || exitDateFrom).trim();
  const entryFromTime = String(body.entry_from_time || body.from_time || '12:00').trim();
  const entryToTime = String(body.entry_to_time || body.to_time || '15:00').trim();
  const exitFromTime = String(body.exit_from_time || body.exit_time || '06:00').trim();
  const exitToTime = String(body.exit_to_time || body.exit_time || '09:00').trim();
  const step = Number(body.step_minutes == null ? 30 : body.step_minutes);
  const product = String(body.product || 'terminal3_garage').trim();
  const requestedId = String(body.request_id || '').trim();

  if (![entryDateFrom,entryDateTo,exitDateFrom,exitDateTo].every(validDate_)) throw new Error('Datas inválidas.');
  if (entryDateTo < entryDateFrom) throw new Error('A data final de entrada precisa ser igual ou posterior à inicial.');
  if (exitDateTo < exitDateFrom) throw new Error('A data final de saída precisa ser igual ou posterior à inicial.');
  if (exitDateTo < entryDateFrom) throw new Error('A faixa de saída termina antes da faixa de entrada.');
  if (![entryFromTime,entryToTime,exitFromTime,exitToTime].every(indigoValidTime_)) throw new Error('Na Indigo os horários precisam terminar em :00 ou :30.');
  if (step !== 30) throw new Error('A busca Indigo usa somente intervalos de 30 minutos.');
  if (!['terminal3_garage','terminal3_flex','terminal2_standard','terminal1','any'].includes(product)) throw new Error('Produto Indigo inválido.');
  if (entryToTime < entryFromTime) throw new Error('O último horário de entrada precisa ser igual ou posterior ao primeiro.');
  if (exitToTime < exitFromTime) throw new Error('O último horário de saída precisa ser igual ou posterior ao primeiro.');

  const estimated = indigoCombinationCount_(entryDateFrom, entryDateTo, entryFromTime, entryToTime, exitDateFrom, exitDateTo, exitFromTime, exitToTime);
  if (!estimated) throw new Error('Nenhuma combinação válida de entrada e saída.');
  const jobId = validJobId_(requestedId) ? requestedId : ('indigo_' + Utilities.getUuid().replace(/-/g, '').slice(0, 16));
  const job = {
    job_id: jobId,
    status: 'queued',
    entry_date_from: entryDateFrom,
    entry_date_to: entryDateTo,
    exit_date_from: exitDateFrom,
    exit_date_to: exitDateTo,
    entry_from_time: entryFromTime,
    entry_to_time: entryToTime,
    exit_from_time: exitFromTime,
    exit_to_time: exitToTime,
    step_minutes: 30,
    product: product,
    combinations: estimated,
    started_at: new Date().toISOString()
  };
  job.search_key = indigoSearchKey_(job);

  const props = PropertiesService.getScriptProperties();
  props.setProperty('INDIGO_JOB_' + jobId, JSON.stringify(job));
  indigoDispatch_(job);
  return {
    job_id: jobId,
    search_key: job.search_key,
    status: 'queued',
    cached: false,
    combinations: estimated,
    large_search: estimated > 1000,
    warning: estimated > 1000 ? 'Pesquisa grande: será processada em lotes e poderá demorar mais.' : null
  };
}

function readIndigoResult_(job) {
  const url = INDIGO_CHECKPOINT_RAW + job.search_key + '.json?t=' + Date.now();
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: { 'Cache-Control': 'no-cache' } });
  if (response.getResponseCode() !== 200) return null;
  try {
    const data = JSON.parse(response.getContentText());
    const q = data.request || {};
    if (String(data.request_id || '') !== String(job.job_id)) return null;
    if (String(data.search_key || '') !== String(job.search_key)) return null;
    if (String(q.entry_date_from || '') !== job.entry_date_from || String(q.entry_date_to || '') !== job.entry_date_to) return null;
    if (String(q.exit_date_from || '') !== job.exit_date_from || String(q.exit_date_to || '') !== job.exit_date_to) return null;
    if (String(q.entry_from_time || '') !== String(job.entry_from_time || '')) return null;
    if (String(q.entry_to_time || '') !== String(job.entry_to_time || '')) return null;
    if (String(q.exit_from_time || '') !== String(job.exit_from_time || '')) return null;
    if (String(q.exit_to_time || '') !== String(job.exit_to_time || '')) return null;
    if (Number(q.step_minutes) !== 30) return null;
    if (String(q.product || '') !== String(job.product || '')) return null;
    return data;
  } catch (err) {
    return null;
  }
}

function readIndigoWorkflowStatus_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${INDIGO_WORKFLOW}/runs?event=workflow_dispatch&per_page=30`;
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: ghHeaders_() });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  const needle = 'Indigo ' + job.job_id + ' ·';
  const run = (data.workflow_runs || []).find(function(item) { return String(item.display_title || '').indexOf(needle) === 0; });
  if (!run) return null;
  return { id: run.id, status: run.status, conclusion: run.conclusion, html_url: run.html_url };
}

function pollIndigoSearch_(jobId) {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('INDIGO_JOB_' + jobId);
  if (!raw) return { job_id: jobId, status: 'error', error: 'Pesquisa Indigo não encontrada ou expirada.' };
  const job = JSON.parse(raw);
  const ageMs = Date.now() - new Date(job.started_at).getTime();
  if (ageMs > 6 * 60 * 60 * 1000) {
    props.deleteProperty('INDIGO_JOB_' + jobId);
    return { job_id: jobId, status: 'error', error: 'A pesquisa Indigo excedeu seis horas. Repita a mesma busca para reaproveitar o checkpoint mais recente.' };
  }

  const result = readIndigoResult_(job);
  if (result && result.status === 'completed') return { job_id: jobId, status: 'done', result: result };
  const run = readIndigoWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    return { job_id: jobId, status: 'error', error: 'A busca Indigo foi interrompida: ' + run.conclusion + '. Ao repetir a mesma pesquisa em até 1 hora, o checkpoint será reaproveitado.', result: result };
  }
  if (result) return { job_id: jobId, status: 'in_progress', result: result, workflow: run };
  return { job_id: jobId, status: run && run.status ? run.status : 'running', combinations: job.combinations, workflow: run };
}
