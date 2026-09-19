// Monitor de disponibilidade Apple Store para retirada em loja.
const APPLE_PART_NUMBER = 'MJW64LL/A';
const APPLE_PRODUCT_NAME = 'iPhone 18 Pro Max 256GB Burgundy';
const APPLE_BUY_URL = 'https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy-unlocked';
const APPLE_PICKUP_ENDPOINT = 'https://www.apple.com/shop/retail/pickup-message';

function appleSafeLocation_(value) {
  const location = String(value || '33647').trim();
  if (!location || location.length > 80 || !/^[A-Za-z0-9 .,'-]+$/.test(location)) return '33647';
  return location;
}

function appleAvailability_(params) {
  const location = appleSafeLocation_(params && params.location);
  const query = [
    'pl=true',
    'mts.0=regular',
    'parts.0=' + encodeURIComponent(APPLE_PART_NUMBER),
    'location=' + encodeURIComponent(location)
  ].join('&');
  const url = APPLE_PICKUP_ENDPOINT + '?' + query;

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
      part_number: APPLE_PART_NUMBER,
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
      part_number: APPLE_PART_NUMBER,
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
      part_number: APPLE_PART_NUMBER,
      location: location,
      checked_at: new Date().toISOString(),
      error: 'A Apple retornou uma resposta que não pôde ser interpretada.'
    };
  }

  const body = data && data.body ? data.body : {};
  const stores = Array.isArray(body.stores) ? body.stores : [];
  const parsed = stores.map(function(store) {
    const availability = store && store.partsAvailability
      ? store.partsAvailability[APPLE_PART_NUMBER]
      : null;
    const regular = availability && availability.messageTypes
      ? availability.messageTypes.regular
      : null;
    const pickupDisplay = String(availability && availability.pickupDisplay || '').toLowerCase();
    const selectionEnabled = !!(regular && regular.storeSelectionEnabled);
    const quote = String(availability && availability.pickupSearchQuote || regular && regular.storePickupQuote || '');
    const quoteNorm = quote.toLowerCase();
    // A Apple pode publicar "Available Tomorrow" mantendo pickupDisplay como
    // unavailable. Isso ainda é estoque reservável para retirada e deve aparecer
    // no monitor, sem confundir com "Currently unavailable".
    const scheduledPickup = /available\s+(today|tomorrow)|ready\s+(today|tomorrow)|pickup.*(today|tomorrow)/i.test(quote);
    const explicitlyUnavailable = /currently\s+unavailable|not\s+available|unavailable/i.test(quoteNorm);
    const available = !!availability && !explicitlyUnavailable && (
      pickupDisplay === 'available' ||
      scheduledPickup ||
      (selectionEnabled && pickupDisplay !== 'unavailable')
    );
    const address = store && store.address ? store.address : {};
    return {
      store_number: String(store && store.storeNumber || ''),
      name: String(store && store.storeName || 'Apple Store'),
      city: String(store && store.city || ''),
      state: String(store && store.state || ''),
      postal_code: String(address.postalCode || ''),
      address: String(address.address2 || ''),
      distance: Number(store && store.storedistance || 0),
      distance_text: String(store && store.storeDistanceWithUnit || ''),
      available: available,
      pickup_display: pickupDisplay || 'unknown',
      quote: quote,
      selection_enabled: selectionEnabled,
      eligible: !!(availability && availability.storePickEligible),
      product_title: String(regular && regular.storePickupProductTitle || APPLE_PRODUCT_NAME),
      reservation_url: String(store && (store.reservationUrl || store.makeReservationUrl) || '')
    };
  });

  const availableStores = parsed.filter(function(store) { return store.available; });
  return {
    ok: true,
    status: 'ok',
    source: 'Apple Store Pickup Availability',
    product: APPLE_PRODUCT_NAME,
    part_number: APPLE_PART_NUMBER,
    location: location,
    checked_at: new Date().toISOString(),
    stores_count: parsed.length,
    available_count: availableStores.length,
    any_available: availableStores.length > 0,
    stores: parsed,
    apple_url: APPLE_BUY_URL
  };
}
