const HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "public, max-age=60",
  "X-Content-Type-Options": "nosniff",
};

export async function onRequestGet({ env }) {
  const snapshot = await env.VITALS.get("snapshot", { cacheTtl: 60 });
  if (!snapshot) {
    return new Response(JSON.stringify({ error: "snapshot unavailable" }), { status: 503, headers: HEADERS });
  }
  return new Response(snapshot, { headers: HEADERS });
}
