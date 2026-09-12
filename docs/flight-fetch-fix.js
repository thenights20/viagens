(() => {
  if (window.__flightDispatchFetchFix) return;
  window.__flightDispatchFetchFix = true;

  const nativeFetch = window.fetch.bind(window);

  function backupBeacon(url, body) {
    try {
      if (!navigator.sendBeacon || typeof body !== 'string') return false;
      const blob = new Blob([body], { type: 'text/plain;charset=UTF-8' });
      return navigator.sendBeacon(url, blob);
    } catch (_) {
      return false;
    }
  }

  window.fetch = function patchedFetch(input, init) {
    try {
      const url = typeof input === 'string' ? input : String(input?.url || '');
      const method = String(init?.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
      const isFlightDispatch = method === 'POST'
        && /script\.google\.com\/macros\/s\//i.test(url)
        && /\/api\/search(?:[/?]|$)/i.test(url);

      if (isFlightDispatch) {
        const options = Object.assign({}, init || {}, {
          mode: 'no-cors',
          cache: 'no-store',
          keepalive: true
        });

        let settled = false;
        nativeFetch(input, options)
          .then(() => { settled = true; })
          .catch(() => {
            settled = true;
            backupBeacon(url, options.body);
          });

        // Se o redirect do Apps Script prender a Promise, envia uma cópia de segurança.
        // A interface segue imediatamente e não fica congelada em 1%.
        setTimeout(() => {
          if (!settled) backupBeacon(url, options.body);
        }, 2500);

        return Promise.resolve({
          ok: true,
          status: 202,
          type: 'opaque',
          json: async () => ({ status: 'queued' }),
          text: async () => ''
        });
      }
    } catch (_) {}

    return nativeFetch(input, init);
  };
})();
