// Use the tunnel in production, localhost in dev
const API_BASE =
  window.location.hostname === "localhost"
    ? (process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000")
    : process.env.REACT_APP_API_BASE; // set in Cloudflare Pages

const API_KEY = process.env.REACT_APP_API_KEY; // set in Pages

export async function loadData() {
  const r = await fetch(`${API_BASE}/api/data`);
  if (!r.ok) throw new Error("data load failed " + r.status);
  return r.json();               // <- contents of Scored_Enriched_clean.json
}

export async function status() {
  const r = await fetch(`${API_BASE}/api/status`);
  if (!r.ok) throw new Error("status failed " + r.status);
  return r.json();               // { running: boolean, pid: number|null }
}

export async function runJob() {
  const r = await fetch(`${API_BASE}/api/run`, {
    method: "POST",
    headers: { "X-Access-Key": API_KEY }
  });
  if (!r.ok) throw new Error("run failed " + r.status);
  return r.json();               // { pid: ... }
}

export async function stopJob() {
  const r = await fetch(`${API_BASE}/api/stop`, {
    method: "POST",
    headers: { "X-Access-Key": API_KEY }
  });
  if (!r.ok) throw new Error("stop failed " + r.status);
  return r.json();
}
