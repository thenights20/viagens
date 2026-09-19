const MILES_WORKFLOW = 'miles-search.yml';
const MILES_RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/miles-search.json';

function validMilesProgram_(value) {
  return ['', 'Smiles', 'LATAM Pass', 'Azul Fidelidade', 'AAdvantage'].includes(String(value || ''));
}

function validMilesCabin_(value) {
  return ['', 'economy', 'premium_economy', 'business', 'first'].includes(String(value || ''));
}

function dispatchMilesSearch_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${MILES_WORKFLOW}/dispatches`;
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
        period_mode: job.period_mode || 'month',
        start_date: job.start_date || '',
        end_date: job.end_date || '',
        program: job.program || '',
        cabin: job.cabin || '',
        request_id: job.job_id
      }
    }),
    headers: ghHeaders_()
  });
  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub recusou a busca por milhas (' + response.getResponseCode() + '): ' + response.getContentText().slice(0, 500));
  }
}

function startMilesSearch_(body) {
  const origin = String(body.origin || '').trim().toUpperCase();
  const destination = String(body.destination || '').trim().toUpperCase();
  let month = String(body.month || '').trim();
  const periodMode = String(body.period_mode || 'month').trim().toLowerCase();
  let startDate = String(body.start_date || '').trim();
  let endDate = String(body.end_date || '').trim();
  const program = String(body.program || '').trim();
  const cabin = String(body.cabin || '').trim();
  const requestedId = String(body.request_id || '').trim();

  if (!/^[A-Z]{3}$/.test(origin) || !/^[A-Z]{3}$/.test(destination)) throw new Error('Origem/destino inválidos.');
  if (origin === destination) throw new Error('Origem e destino não podem ser iguais.');
  if (!['month', 'range'].includes(periodMode)) throw new Error('Tipo de período inválido.');
  if (!validMilesProgram_(program)) throw new Error('Programa de milhas inválido.');
  if (!validMilesCabin_(cabin)) throw new Error('Cabine inválida.');

  if (periodMode === 'range') {
    if (!validDate_(startDate) || !validDate_(endDate)) throw new Error('Datas do intervalo inválidas.');
    if (endDate < startDate) throw new Error('A data final precisa ser igual ou posterior à data inicial.');
    month = startDate.slice(0, 7);
  } else {
    if (!/^20\d\d-(0[1-9]|1[0-2])$/.test(month)) throw new Error('Mês inválido.');
    startDate = '';
    endDate = '';
  }

  const jobId = validJobId_(requestedId) ? requestedId : 'miles_' + Utilities.getUuid().replace(/-/g, '').slice(0, 16);
  const job = {
    job_id: jobId,
    status: 'queued',
    origin: origin,
    destination: destination,
    month: month,
    period_mode: periodMode,
    start_date: startDate,
    end_date: endDate,
    program: program,
    cabin: cabin,
    started_at: new Date().toISOString()
  };

  const props = PropertiesService.getScriptProperties();
  props.setProperty('MILES_JOB_' + jobId, JSON.stringify(job));
  setProgress_(jobId, {
    status: 'received',
    stage: 'received',
    percent: 0,
    completed: 0,
    priced: 0,
    message: 'Solicitação de milhas recebida pelo serviço.'
  });

  try {
    dispatchMilesSearch_(job);
    setProgress_(jobId, {
      status: 'queued',
      stage: 'queued',
      percent: 0,
      message: 'GitHub aceitou a busca por milhas.'
    });
  } catch (err) {
    props.deleteProperty('MILES_JOB_' + jobId);
    setProgress_(jobId, { status: 'error', stage: 'error', percent: 0, error: String(err.message || err) });
    throw err;
  }
  return { job_id: jobId, status: 'queued', cached: false };
}

function milesResultMatches_(data, job) {
  if (!data || String(data.request_id || '') !== String(job.job_id)) return false;
  const request = data.request || {};
  if (request.origin !== job.origin || request.destination !== job.destination) return false;
  if ((request.period_mode || 'month') !== (job.period_mode || 'month')) return false;
  if (String(request.program || '') !== String(job.program || '')) return false;
  if (String(request.cabin || '') !== String(job.cabin || '')) return false;
  if ((job.period_mode || 'month') === 'range') {
    return request.start_date === job.start_date && request.end_date === job.end_date;
  }
  return request.month === job.month;
}

function readMilesResult_(job) {
  const response = UrlFetchApp.fetch(MILES_RESULT_RAW + '?t=' + Date.now(), {
    muteHttpExceptions: true,
    headers: { 'Cache-Control': 'no-cache' }
  });
  if (response.getResponseCode() !== 200) return null;
  try {
    const data = JSON.parse(response.getContentText());
    return milesResultMatches_(data, job) ? data : null;
  } catch (err) {
    return null;
  }
}

function readMilesWorkflowStatus_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${MILES_WORKFLOW}/runs?event=workflow_dispatch&per_page=20`;
  const response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: ghHeaders_()
  });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  const needle = 'Milhas ' + job.job_id + ' ·';
  const run = (data.workflow_runs || []).find(r => String(r.display_title || '').indexOf(needle) === 0);
  if (!run) return null;
  return { id: run.id, status: run.status, conclusion: run.conclusion, html_url: run.html_url };
}

function pollMilesSearch_(jobId) {
  const key = 'MILES_JOB_' + jobId;
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty(key);
  if (!raw) return { job_id: jobId, status: 'error', error: 'Busca por milhas não encontrada ou expirada.' };

  const job = JSON.parse(raw);
  const ageMs = Date.now() - new Date(job.started_at).getTime();
  if (ageMs > 30 * 60 * 1000) {
    props.deleteProperty(key);
    return { job_id: jobId, status: 'error', error: 'A busca por milhas excedeu 30 minutos.' };
  }

  const result = readMilesResult_(job);
  if (result) {
    if (result.status === 'error') {
      setProgress_(jobId, { status: 'error', stage: 'error', percent: 100, error: result.error || 'Falha na busca por milhas.' });
      return { job_id: jobId, status: 'error', error: result.error || 'Falha na busca por milhas.', result: result };
    }
    setProgress_(jobId, {
      status: 'done',
      stage: 'done',
      percent: 100,
      completed: Number(result.result_count || 0),
      priced: Number(result.result_count || 0),
      message: 'Busca por milhas concluída.'
    });
    return { job_id: jobId, status: 'done', result: result };
  }

  const run = readMilesWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    setProgress_(jobId, {
      status: 'error',
      stage: 'error',
      percent: 100,
      error: 'A busca por milhas terminou com erro no servidor: ' + (run.conclusion || 'erro')
    });
    return {
      job_id: jobId,
      status: 'error',
      error: 'A busca por milhas terminou com erro no servidor: ' + (run.conclusion || 'erro')
    };
  }

  return {
    job_id: jobId,
    status: run && run.status ? run.status : 'running',
    run_url: run && run.html_url ? run.html_url : ''
  };
}
