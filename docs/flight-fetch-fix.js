(() => {
  if (window.__flightDispatchFetchFix) return;
  window.__flightDispatchFetchFix = true;

  const nativeFetch = window.fetch.bind(window);

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

        // O Apps Script recebe a solicitação normalmente, mas a resposta dele pode
        // ficar presa em um redirect cross-origin. A busca não deve esperar por isso.
        nativeFetch(input, options).catch(() => {});

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
