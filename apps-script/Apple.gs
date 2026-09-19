// Monitor de disponibilidade Apple Store para retirada em loja.
const APPLE_PRODUCTS = [
  { storage: '256GB', part_number: 'MJW64LL/A', url: 'https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy-unlocked' },
  { storage: '512GB', part_number: '', url: 'https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-512gb-burgundy' }
];

function appleResolvePartNumber_(product) {
  if (product.part_number) return product.part_number;
  const cache = CacheService.getScriptCache();
  const key = 'APPLE_PART_STRICT_' + product.storage;
  const cached = cache.get(key);
  if (cached) return cached;
  try {
    const response = UrlFetchApp.fetch(product.url, {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: { 'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9' }
    });
    const html = response.getContentText();
    const wantedStorage = String(product.storage || '').toLowerCase();
    const wantedColor = 'burgundy';
    const candidates = [];
    const partRe = /[A-Z0-9]{5,12}LL\\?\/A/gi;
    let m;
    while ((m = partRe.exec(html)) !== null) {
      const part = String(m[0]).replace('\\/', '/');
      const from = Math.max(0, m.index - 1200);
      const to = Math.min(html.length, m.index + 1200);
      const ctx = html.slice(from, to).toLowerCase();
      if (ctx.indexOf(wantedStorage) >= 0 && ctx.indexOf(wantedColor) >= 0 &&
          (ctx.indexOf('pro max') >= 0 || ctx.indexOf('6.9-inch') >= 0)) {
        candidates.push(part);
      }
    }
    const unique = candidates.filter(function(v, i, a) { return a.indexOf(v) === i; });
    if (unique.length === 1) {
      cache.put(key, unique[0], 1800);
      return unique[0];
    }
  } catch (err) {}
  return '';
}

function appleConfiguredProducts_() {
  return APPLE_PRODUCTS.map(function(p) {
    return { storage: p.storage, part_number: appleResolvePartNumber_(p), url: p.url };
  }).filter(function(p) { return p.part_number; });
}
const APPLE_PRODUCT_NAME = 'iPhone 18 Pro Max Burgundy';
const APPLE_BUY_URL = 'https://www.apple.com/shop/buy-iphone/iphone-18-pro';
const APPLE_PICKUP_ENDPOINT = 'https://www.apple.com/shop/retail/pickup-message';

function appleSafeLocation_(value) {
  const location = String(value || '33647').trim();
  if (!location || location.length > 80 || !/^[A-Za-z0-9 .,'-]+$/.test(location)) return '33647';
  return location;
}

function appleAvailability_(params) {
  const location = appleSafeLocation_(params && params.location);
  const configured = appleConfiguredProducts_();
  const query = ['pl=true', 'mts.0=regular'];
  configured.forEach(function(p, i) {
    query.push('parts.' + i + '=' + encodeURIComponent(p.part_number));
  });
  query.push('location=' + encodeURIComponent(location));
  const url = APPLE_PICKUP_ENDPOINT + '?' + query.join('&');

  let response;
  try {
    response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true,
      followRedirects: true,
      headers: {
        'Accept': 'application/json,text/plain,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache, no-store, max-age=0',
        'Pragma': 'no-cache',
        'Referer': APPLE_BUY_URL,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
      }
    });
  } catch (err) {
    return {
      ok: false,
      status: 'error',
      product: APPLE_PRODUCT_NAME,
      part_numbers: configured.map(function(p) { return p.part_number; }),
      location: location,
      checked_at: new Date().toISOString(),
      error: 'Falha ao consultar a Apple: ' + String(err && err.message ? err.message : err)
    };
  }

  const code = response.getResponseCode();
  const raw = response.getContentText();
  if (code !== 200) {
    return {
      ok: false,
      status: (code === 429 || code === 541) ? 'blocked' : 'error',
      blocked: code === 429 || code === 541,
      http_status: code,
      product: APPLE_PRODUCT_NAME,
      part_numbers: configured.map(function(p) { return p.part_number; }),
      location: location,
      checked_at: new Date().toISOString(),
      error: (code === 429 || code === 541)
        ? 'A Apple limitou temporariamente as consultas. O monitor vai desacelerar e tentar novamente.'
        : 'A Apple respondeu com HTTP ' + code + '.'
    };
  }

  let data;
  try {
    data = JSON.parse(raw);
  } catch (err) {
    return {
      ok: false,
      status: 'error',
      http_status: code,
      product: APPLE_PRODUCT_NAME,
      part_numbers: configured.map(function(p) { return p.part_number; }),
      location: location,
      checked_at: new Date().toISOString(),
      error: 'A Apple retornou uma resposta que não pôde ser interpretada.'
    };
  }

  const body = data && data.body ? data.body : {};
  const stores = Array.isArray(body.stores) ? body.stores : [];
  const parsed = [];
  stores.forEach(function(store) {
    const address = store && store.address ? store.address : {};
    configured.forEach(function(product) {
      const availability = store && store.partsAvailability
        ? store.partsAvailability[product.part_number]
        : null;
      const regular = availability && availability.messageTypes
        ? availability.messageTypes.regular
        : null;
      const pickupDisplay = String(availability && availability.pickupDisplay || '').toLowerCase();
      const selectionEnabled = !!(regular && regular.storeSelectionEnabled);
      const quote = String(availability && availability.pickupSearchQuote || regular && regular.storePickupQuote || '');
      const quoteNorm = quote.toLowerCase();
      const scheduledPickup = /available\s+(today|tomorrow)|ready\s+(today|tomorrow)|pickup.*(today|tomorrow)/i.test(quote);
      const explicitlyUnavailable = /currently\s+unavailable|not\s+available|unavailable/i.test(quoteNorm);
      const identityText = [regular && regular.storePickupProductTitle, availability && availability.partNumber, product.storage, APPLE_PRODUCT_NAME].join(' ').toLowerCase();
      const exactVariant = identityText.indexOf('512gb') < 0 || (identityText.indexOf('burgundy') >= 0 && (identityText.indexOf('pro max') >= 0 || identityText.indexOf('iphone 18') >= 0));
      const available = exactVariant && !!availability && !explicitlyUnavailable && (
        pickupDisplay === 'available' ||
        scheduledPickup ||
        (selectionEnabled && pickupDisplay !== 'unavailable')
      );
      parsed.push({
        store_number: String(store && store.storeNumber || ''),
        name: String(store && store.storeName || 'Apple Store'),
        city: String(store && store.city || ''),
        state: String(store && store.state || ''),
        postal_code: String(address.postalCode || ''),
        address: String(address.address2 || ''),
        distance: Number(store && store.storedistance || 0),
        distance_text: String(store && store.storeDistanceWithUnit || ''),
        storage: product.storage,
        part_number: product.part_number,
        available: available,
        pickup_display: pickupDisplay || 'unknown',
        quote: quote,
        selection_enabled: selectionEnabled,
        eligible: !!(availability && availability.storePickEligible),
        product_title: String(regular && regular.storePickupProductTitle || (APPLE_PRODUCT_NAME + ' ' + product.storage)),
        reservation_url: String(store && (store.reservationUrl || store.makeReservationUrl) || '')
      });
    });
  });

  const availableStores = parsed.filter(function(store) { return store.available; });
  return {
    ok: true,
    status: 'ok',
    source: 'Apple Store Pickup Availability',
    product: APPLE_PRODUCT_NAME,
    part_numbers: configured.map(function(p) { return p.part_number; }),
    location: location,
    checked_at: new Date().toISOString(),
    stores_count: stores.length,
    checked_variants: configured.map(function(p) { return p.storage; }),
    missing_variants: APPLE_PRODUCTS.filter(function(p) { return !configured.some(function(c) { return c.storage === p.storage; }); }).map(function(p) { return p.storage; }),
    available_count: availableStores.length,
    any_available: availableStores.length > 0,
    stores: parsed,
    apple_url: APPLE_BUY_URL
  };
}
