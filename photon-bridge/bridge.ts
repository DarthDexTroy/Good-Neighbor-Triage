/**
 * Photon (Spectrum) <-> LifeLine backend bridge.
 *
 *   inbound:  iMessage -> Spectrum -> POST {BACKEND_URL}/api/photon/inbound {from, text, channel}
 *   outbound: backend messenger -> POST http://localhost:{BRIDGE_PORT}/send {to, text} -> space.send(text)
 *
 * Shared iMessage lines can't text first, so we can only send into a conversation the person opened.
 * Spaces are remembered by the last 10 digits of the sender's handle.
 *
 * Run: cd photon-bridge && npm start   (reads photon-bridge/.env)
 */
import { createServer } from "node:http";
import { Spectrum } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BRIDGE_PORT = Number(process.env.BRIDGE_PORT ?? 8787);

const key = (handle: string) => handle.replace(/\D/g, "").slice(-10) || handle.toLowerCase();
const spaces = new Map<string, { space: any; handle: string }>();

const app = await Spectrum({
  projectId: process.env.SPECTRUM_PROJECT_ID!,
  projectSecret: process.env.SPECTRUM_PROJECT_SECRET!,
  providers: [imessage.config()],
});
console.log(`[bridge] Spectrum connected. Outbound on :${BRIDGE_PORT}, inbound -> ${BACKEND_URL}`);

createServer(async (req, res) => {
  const reply = (code: number, body: object) => {
    res.writeHead(code, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };
  if (req.method === "GET" && req.url === "/health") {
    return reply(200, { ok: true, conversations: [...spaces.values()].map((s) => `…${s.handle.slice(-4)}`) });
  }
  if (req.method !== "POST" || req.url !== "/send") return reply(404, { error: "not found" });
  let raw = "";
  for await (const chunk of req) raw += chunk;
  try {
    const { to, text } = JSON.parse(raw);
    const entry = spaces.get(key(String(to)));
    if (!entry) return reply(409, { error: `No conversation with …${String(to).slice(-4)} yet: they must text the line first` });
    await entry.space.send(String(text));
    console.log(`[bridge] -> …${entry.handle.slice(-4)}: ${String(text).slice(0, 60)}`);
    return reply(200, { ok: true });
  } catch (e: any) {
    console.error("[bridge] send failed:", e?.message ?? e);
    return reply(502, { error: String(e?.message ?? e) });
  }
}).listen(BRIDGE_PORT);

for await (const [space, message] of app.messages) {
  try {
    const handle = message.sender?.id;
    if (!handle) continue;
    spaces.set(key(handle), { space, handle });
    const c: any = message.content;
    const text = c?.type === "text" ? c.text : ["attachment", "image", "file"].includes(c?.type) ? "[photo]" : "";
    if (!text) continue;
    console.log(`[bridge] <- …${handle.slice(-4)}: ${text.slice(0, 60)}`);
    const r = await fetch(`${BACKEND_URL}/api/photon/inbound`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: handle, text, channel: "imessage" }),
    });
    if (!r.ok) console.error(`[bridge] backend ${r.status}: ${await r.text()}`);
  } catch (e: any) {
    console.error("[bridge] inbound failed:", e?.message ?? e);
  }
}
