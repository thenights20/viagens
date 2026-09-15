const INDIGO_WORKFLOW = 'indigo-parking-search.yml';
const INDIGO_RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/indigo-parking-search.json';

function indigoValidTime_(value) {
  return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(String(value || ''));
}

function indigoMinutes_(value) {
  const p = String(value || '').split(':').map(Number);
  return p[0] * 60 + p[1];
}

function indigoSlotCount_(fromTime, toTime, step) {
  return Math.floor((indigoMinutes_(toTime) - indigoMinutes_(fromTime)) / step) + 1;
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
  if (![entryFromTime,entryToTime,exitFromTime,exitToTime].every(indigoValidTime_)) throw new Error('Horário inválido.');
  if (![30, 60].includes(step)) throw new Error('Intervalo deve ser 30 ou 60 minutos.');
  if (!['terminal3_garage','terminal3_flex','terminal2_standard','terminal1','any'].includes(product)) throw new Error('Produto Indigo inválido.');
  if (entryToTime < entryFromTime) throw new Error('O último horário de entrada precisa ser igual ou posterior ao primeiro.');
  if (exitToTime < exitFromTime) throw new Error('O último horário de saída precisa ser igual ou posterior ao primeiro.');
  const dayCount = function(a,b){ return Math.floor((new Date(b + 'T12:00:00Z').getTime() - new Date(a + 'T12:00:00Z').getTime()) / 86400000) + 1; };
  const entryDays = dayCount(entryDateFrom, entryDateTo);
  const exitDays = dayCount(exitDateFrom, exitDateTo);
  if (entryDays > 7 || exitDays > 7) throw new Error('Cada faixa de datas pode ter no máximo 7 dias.');
  const estimated = entryDays * exitDays * indigoSlotCount_(entryFromTime, entryToTime, step) * indigoSlotCount_(exitFromTime, exitToTime, step);
  if (estimated > 3000) throw new Error('Essa faixa pode gerar até ' + estimated + ' combinações. O máximo por varredura é 3000. Reduza datas ou horários.');

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
    step_minutes: step,
    product: product,
    started_at: new Date().toISOString()
  };

  const props = PropertiesService.getScriptProperties();
  props.setProperty('INDIGO_JOB_' + jobId, JSON.stringify(job));
  indigoDispatch_(job);
  return { job_id: jobId, status: 'queued', cached: false, combinations: estimated };
}

function readIndigoResult_(job) {
  const response = UrlFetchApp.fetch(INDIGO_RESULT_RAW + '?t=' + Date.now(), {
    muteHttpExceptions: true,
    headers: { 'Cache-Control': 'no-cache' }
  });
  if (response.getResponseCode() !== 200) return null;
  try {
    const data = JSON.parse(response.getContentText());
    const q = data.request || {};
    if (String(data.request_id || '') !== String(job.job_id)) return null;
    if (String(q.entry_date_from || q.entry_date || '') !== job.entry_date_from || String(q.entry_date_to || q.entry_date || '') !== job.entry_date_to) return null;
    if (String(q.exit_date_from || q.exit_date || '') !== job.exit_date_from || String(q.exit_date_to || q.exit_date || '') !== job.exit_date_to) return null;
    if (String(q.entry_from_time || q.from_time || '') !== String(job.entry_from_time || '')) return null;
    if (String(q.entry_to_time || q.to_time || '') !== String(job.entry_to_time || '')) return null;
    if (String(q.exit_from_time || q.exit_time || '') !== String(job.exit_from_time || '')) return null;
    if (String(q.exit_to_time || q.exit_time || '') !== String(job.exit_to_time || '')) return null;
    if (Number(q.step_minutes) !== Number(job.step_minutes)) return null;
    if (String(q.product || '') !== String(job.product || '')) return null;
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
  if (ageMs > 60 * 60 * 1000) {
    props.deleteProperty('INDIGO_JOB_' + jobId);
    return { job_id: jobId, status: 'error', error: 'A pesquisa Indigo excedeu 60 minutos.' };
  }

  const result = readIndigoResult_(job);
  if (result) return { job_id: jobId, status: 'done', result: result };

  const run = readIndigoWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    return { job_id: jobId, status: 'error', error: 'A busca Indigo terminou com erro: ' + run.conclusion };
  }
  return { job_id: jobId, status: run && run.status ? run.status : 'running' };
}
