const SUPABASE_URL  = 'https://zxjhgcumweqaxcemoiga.supabase.co';
const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp4amhnY3Vtd2VxYXhjZW1vaWdhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0MTExNjksImV4cCI6MjA5Nzk4NzE2OX0.vRETMCzDvd0HONqz9rlDXFqrF_ZQP_kp-wURphltsQo';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { exam, answers, seed, device } = req.body;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);

    const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/enqueue_print`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON,
        'Authorization': `Bearer ${SUPABASE_ANON}`,
      },
      body: JSON.stringify({
        p_exam:    exam    || '공무원',
        p_answers: answers || [],
        p_cur:     null,
        p_device:  device  || null,
        p_seed:    seed != null ? Number(seed) : null,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    const text = await r.text();
    console.log('[print] status:', r.status, 'body:', text);
    const data = JSON.parse(text);
    return res.status(r.ok ? 200 : 500).json(data);
  } catch (e) {
    console.error('[print] error:', e.message);
    return res.status(500).json({ error: e.message });
  }
}
