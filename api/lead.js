// Same-origin relay for the booking form -> GoHighLevel inbound webhook.
//
// The form used to POST straight to services.leadconnectorhq.com from the browser.
// Ad/privacy blockers (uBlock, Brave Shields, Ghostery…) block that host, and the
// lead was lost silently. Browsers never block same-origin requests, so the form
// now POSTs here and this function forwards the identical JSON to GHL.
// Runs as a Vercel Function (api/ directory); nothing is stored here.

const WEBHOOK = 'https://services.leadconnectorhq.com/hooks/0G5r7THzw7gjg3OextOo/webhook-trigger/dOltIjaGRmcprw0mI8y6';
const MAX_BYTES = 64 * 1024;

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.status(405).json({ ok: false, error: 'POST only' });
    return;
  }
  let data = req.body;
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch { data = null; }
  }
  if (!data || typeof data !== 'object' || JSON.stringify(data).length > MAX_BYTES) {
    res.status(400).json({ ok: false, error: 'bad payload' });
    return;
  }
  if (!String(data.name || data.full_name || '').trim() || !String(data.mobile || data.phone || '').trim()) {
    res.status(400).json({ ok: false, error: 'name and mobile are required' });
    return;
  }
  data.relay = 'vercel:/api/lead';
  data.client_ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 12000);
    const r = await fetch(WEBHOOK, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      signal: ctrl.signal,
    });
    clearTimeout(t);
    if (!r.ok) {
      console.error('GHL webhook HTTP', r.status, 'submission', data.submission_id);
      res.status(502).json({ ok: false, error: 'webhook ' + r.status });
      return;
    }
    console.log('lead relayed', data.submission_id, data.service, data.gclid ? 'gclid' : (data.gbraid ? 'gbraid' : 'no-click-id'));
    res.status(200).json({ ok: true });
  } catch (e) {
    console.error('GHL webhook failed', String(e), 'submission', data.submission_id);
    res.status(502).json({ ok: false, error: 'webhook unreachable' });
  }
}
