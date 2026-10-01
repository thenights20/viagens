const RENTCARS_WORKFLOW = 'rentcars-time-search.yml';
const RENTCARS_RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/rentcars/';

function rentcarsValidTime_(value) {
  return /^(?:[01]\d|2[0-3]):(?:00|30)$/.test(String(value || ''));
}

function rentcarsMinutes_(value) {
  const p = String(value || '').split(':').map(Number);
  return p[0] * 60 + p[1];
}

function rentcarsTimeCount_(fromTime, toTime) {
  if (!rentcarsValidTime_(fromTime) || !rentcarsValidTime_(toTime) || rentcarsMinutes_(toTime) < rentcarsMinutes_(fromTime)) return 0;
  return Math.floor((rentcarsMinutes_(toTime) - rentcarsMinutes_(fromTime)) / 30) + 1;
}

function rentcarsSearchKey_(job) {
  const canonical = [
    'v1', job.pickup_location, job.dropoff_location, job.pickup_date, job.dropoff_date,
    job.pickup_from_time, job.pickup_to_time, job.dropoff_from_time, job.dropoff_to_time,
    job.mode, job.currency, job.driver_age, '30'
  ].join('|');
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, canonical, Utilities.Charset.UTF_8)
    .map(function(value) { return ('0' + ((value + 256) % 256).toString(16)).slice(-2); }).join('');
}

function rentcarsDispatch_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${RENTCARS_WORKFLOW}/dispatches`;
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    payload: JSON.stringify({
      ref: 'main',
      inputs: {
        pickup_location: job.pickup_location,
        dropoff_location: job.dropoff_location,
        pickup_date: job.pickup_date,
        dropoff_date: job.dropoff_date,
        pickup_from_time: job.pickup_from_time,
        pickup_to_time: job.pickup_to_time,
        dropoff_from_time: job.dropoff_from_time,
        dropoff_to_time: job.dropoff_to_time,
        mode: job.mode,
        currency: job.currency,
        driver_age: String(job.driver_age),
        request_id: job.job_id,
        search_key: job.search_key
      }
    }),
    headers: ghHeaders_()
  });
  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub recusou a pesquisa Rentcars (' + response.getResponseCode() + '): ' + response.getContentText().slice(0, 500));
  }
}

function startRentcarsSearch_(body) {
  const pickupLocation = String(body.pickup_location || '').trim();
  const dropoffLocation = String(body.dropoff_location || '').trim();
  const pickupDate = String(body.pickup_date || '').trim();
  const dropoffDate = String(body.dropoff_date || '').trim();
  const pickupFrom = String(body.pickup_from_time || '08:00').trim();
  const pickupTo = String(body.pickup_to_time || pickupFrom).trim();
  const dropoffFrom = String(body.dropoff_from_time || '10:00').trim();
  const mode = String(body.mode || 'pickup').trim();
  const dropoffTo = mode === 'pickup' ? dropoffFrom : String(body.dropoff_to_time || dropoffFrom).trim();
  const currency = String(body.currency || 'BRL').trim().toUpperCase();
  const driverAge = Number(body.driver_age == null ? 30 : body.driver_age);
  const step = Number(body.step_minutes == null ? 30 : body.step_minutes);
  const requestedId = String(body.request_id || '').trim();

  if (!pickupLocation || !dropoffLocation || pickupLocation.length > 160 || dropoffLocation.length > 160) throw new Error('Informe locais válidos de retirada e devolução.');
  if (!validDate_(pickupDate) || !validDate_(dropoffDate) || dropoffDate < pickupDate) throw new Error('Datas de locação inválidas.');
  if (![pickupFrom,pickupTo,dropoffFrom,dropoffTo].every(rentcarsValidTime_)) throw new Error('Os horários precisam terminar em :00 ou :30.');
  if (rentcarsMinutes_(pickupTo) < rentcarsMinutes_(pickupFrom) || rentcarsMinutes_(dropoffTo) < rentcarsMinutes_(dropoffFrom)) throw new Error('Faixa de horários inválida.');
  if (!['pickup','both'].includes(mode)) throw new Error('Modo de otimização inválido.');
  if (!['BRL','USD'].includes(currency)) throw new Error('Moeda inválida.');
  if (!Number.isInteger(driverAge) || driverAge < 18 || driverAge > 80) throw new Error('Idade do motorista inválida.');
  if (step !== 30) throw new Error('A pesquisa Rentcars usa intervalos de 30 minutos.');

  const combinations = rentcarsTimeCount_(pickupFrom,pickupTo) * rentcarsTimeCount_(dropoffFrom,dropoffTo);
  if (!combinations) throw new Error('Nenhuma combinação válida de horários.');
  if (combinations > 49) throw new Error('Limite de 49 combinações por pesquisa. Reduza a faixa de horários.');

  const jobId = validJobId_(requestedId) ? requestedId : ('rentcars_' + Utilities.getUuid().replace(/-/g, '').slice(0, 16));
  const job = {
    job_id: jobId,
    pickup_location: pickupLocation,
    dropoff_location: dropoffLocation,
    pickup_date: pickupDate,
    dropoff_date: dropoffDate,
    pickup_from_time: pickupFrom,
    pickup_to_time: pickupTo,
    dropoff_from_time: dropoffFrom,
    dropoff_to_time: dropoffTo,
    mode: mode,
    currency: currency,
    driver_age: driverAge,
    combinations: combinations,
    started_at: new Date().toISOString()
  };
  job.search_key = rentcarsSearchKey_(job);
  PropertiesService.getScriptProperties().setProperty('RENTCARS_JOB_' + jobId, JSON.stringify(job));
  rentcarsDispatch_(job);
  return { job_id: jobId, search_key: job.search_key, status: 'queued', combinations: combinations, source: 'Rentcars' };
}

function readRentcarsResult_(job) {
  const url = RENTCARS_RESULT_RAW + job.search_key + '.json?t=' + Date.now();
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: { 'Cache-Control': 'no-cache' } });
  if (response.getResponseCode() !== 200) return null;
  try {
    const data = JSON.parse(response.getContentText());
    const q = data.request || {};
    if (String(data.request_id || '') !== String(job.job_id)) return null;
    if (String(data.search_key || '') !== String(job.search_key)) return null;
    if (String(data.source || '') !== 'Rentcars') return null;
    if (String(q.pickup_location || '') !== job.pickup_location || String(q.dropoff_location || '') !== job.dropoff_location) return null;
    if (String(q.pickup_date || '') !== job.pickup_date || String(q.dropoff_date || '') !== job.dropoff_date) return null;
    return data;
  } catch (err) {
    return null;
  }
}

function readRentcarsWorkflowStatus_(job) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${RENTCARS_WORKFLOW}/runs?event=workflow_dispatch&per_page=30`;
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: ghHeaders_() });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  const needle = 'Rentcars ' + job.job_id + ' ·';
  const run = (data.workflow_runs || []).find(function(item) { return String(item.display_title || '').indexOf(needle) === 0; });
  if (!run) return null;
  return { id: run.id, status: run.status, conclusion: run.conclusion, html_url: run.html_url };
}

function pollRentcarsSearch_(jobId) {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('RENTCARS_JOB_' + jobId);
  if (!raw) return { job_id: jobId, status: 'error', error: 'Pesquisa Rentcars não encontrada ou expirada.' };
  const job = JSON.parse(raw);
  const ageMs = Date.now() - new Date(job.started_at).getTime();
  if (ageMs > 6 * 60 * 60 * 1000) {
    props.deleteProperty('RENTCARS_JOB_' + jobId);
    return { job_id: jobId, status: 'error', error: 'A pesquisa Rentcars excedeu seis horas.' };
  }
  const result = readRentcarsResult_(job);
  if (result && result.status === 'completed') return { job_id: jobId, status: 'done', result: result };
  if (result && result.status === 'blocked') return { job_id: jobId, status: 'blocked', error: result.error || 'A Rentcars exigiu verificação humana.', result: result };
  const run = readRentcarsWorkflowStatus_(job);
  if (run && run.status === 'completed' && run.conclusion !== 'success') {
    return { job_id: jobId, status: 'error', error: 'A busca Rentcars foi interrompida: ' + run.conclusion + '.', result: result, workflow: run };
  }
  if (result) return { job_id: jobId, status: 'in_progress', result: result, workflow: run };
  return { job_id: jobId, status: run && run.status ? run.status : 'running', combinations: job.combinations, workflow: run };
}
