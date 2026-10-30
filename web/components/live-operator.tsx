"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check, CheckCheck, Headset, Paperclip, Send, X } from "lucide-react";
import { Spinner } from "./ui/bits";
import { api, errorMessage, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Msg = {
  id: number; sender: "player" | "operator"; body: string; operator: string | null; created_at: string;
  kind: "text" | "photo" | "video"; file: string | null; pending?: boolean;
};
type ChatState = { enabled: boolean; messages: Msg[]; unread: number; seen_upto: number; online: boolean; typing: boolean };

const MAX = 1000;
const PHOTO_MAX = 5 * 1024 * 1024;
const VIDEO_MAX = 20 * 1024 * 1024;
const POLL_OPEN_MS = 1500;
const POLL_CLOSED_MS = 8000;
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** One tick = on its way, two grey ticks = delivered to the team, two blue ticks = the team has seen it. */
function Ticks({ state }: { state: "sending" | "delivered" | "seen" }) {
  if (state === "sending") return <Check className="inline h-3.5 w-3.5 text-white/50" aria-label="Sending" />;
  if (state === "delivered") return <CheckCheck className="inline h-3.5 w-3.5 text-white/60" aria-label="Delivered to the team" />;
  return <CheckCheck className="inline h-3.5 w-3.5 text-sky-300" aria-label="Seen by the team" />;
}

/** Floating "Live Operator" button + chat panel. The team answers from a Telegram group; replies appear here. */
export function LiveOperator() {
  const { player } = useAuth();
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [unread, setUnread] = useState(0);
  const [seenUpto, setSeenUpto] = useState(0);
  const [online, setOnline] = useState(false);
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState("");
  const [file, setFile] = useState<{ file: File; url: string; kind: "photo" | "video" } | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const lastId = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const openRef = useRef(open);
  openRef.current = open;

  const merge = useCallback((incoming: Msg[]) => {
    if (!incoming.length) return;
    setMessages((cur) => {
      const have = new Set(cur.filter((m) => !m.pending).map((m) => m.id));
      const fresh = incoming.filter((m) => !have.has(m.id));
      return fresh.length ? [...cur.filter((m) => !m.pending), ...fresh, ...cur.filter((m) => m.pending)] : cur;
    });
    lastId.current = Math.max(lastId.current, ...incoming.map((m) => m.id));
  }, []);

  const markRead = useCallback(() => {
    setUnread(0);
    api("/chat/read", { method: "POST" }).catch(() => {});
  }, []);

  const poll = useCallback(async () => {
    try {
      const s = await api<ChatState>(`/chat${lastId.current ? `?after=${lastId.current}` : ""}`);
      setEnabled(s.enabled);
      merge(s.messages);
      setSeenUpto(s.seen_upto); setOnline(s.online); setTyping(s.typing);
      setLoaded(true);
      if (openRef.current) { if (s.unread > 0) markRead(); } else setUnread(s.unread);
    } catch { /* offline or signed out: try again on the next tick */ }
  }, [merge, markRead]);

  // Reset when the signed-in player changes.
  useEffect(() => {
    lastId.current = 0; setMessages([]); setUnread(0); setSeenUpto(0); setLoaded(false); setEnabled(player ? null : false);
  }, [player?.id]);

  // Poll: quickly while the panel is open, slowly otherwise, and not at all while the tab is hidden.
  useEffect(() => {
    if (!player) return;
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const tick = async () => {
      if (!document.hidden) await poll();
      if (!stopped) timer = setTimeout(tick, openRef.current ? POLL_OPEN_MS : POLL_CLOSED_MS);
    };
    tick();
    return () => { stopped = true; clearTimeout(timer); };
  }, [player, poll, open]);

  useEffect(() => { if (open && player) { markRead(); poll(); } }, [open, player, markRead, poll]);
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: reduce ? "auto" : "smooth" }); }, [messages, open, typing, reduce]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  useEffect(() => () => { if (file) URL.revokeObjectURL(file.url); }, [file]);

  const pickFile = (f: File | undefined) => {
    if (!f) return;
    setError(null);
    const isPhoto = /^image\/(jpeg|png|webp)$/.test(f.type);
    const isVideo = /^video\/(mp4|quicktime|webm)$/.test(f.type);
    if (!isPhoto && !isVideo) { setError("Send a photo (JPEG, PNG, WebP) or a video (MP4, MOV, WebM)."); return; }
    if (f.size > (isPhoto ? PHOTO_MAX : VIDEO_MAX)) { setError(`That ${isPhoto ? "photo" : "video"} is too large. The limit is ${isPhoto ? 5 : 20} MB.`); return; }
    setFile({ file: f, url: URL.createObjectURL(f), kind: isPhoto ? "photo" : "video" });
  };

  const send = async () => {
    const body = text.trim();
    if ((!body && !file) || sending) return;
    setSending(true); setError(null);
    const tempId = -Date.now();
    const attach = file;
    setMessages((cur) => [...cur, { id: tempId, sender: "player", body, operator: null, created_at: new Date().toISOString(), kind: attach?.kind ?? "text", file: attach?.url ?? null, pending: true }]);
    setText(""); setFile(null);
    try {
      let m: Msg;
      if (attach) {
        const form = new FormData();
        form.append("file", attach.file);
        if (body) form.append("caption", body);
        m = await upload<Msg>("/chat/attachments", form);
      } else {
        m = await api<Msg>("/chat/messages", { method: "POST", body: { text: body } });
      }
      setMessages((cur) => cur.filter((x) => x.id !== tempId));
      merge([m]);
      poll();   // pick up any reply right away
    } catch (e) {
      setMessages((cur) => cur.filter((x) => x.id !== tempId));
      setText(body); if (attach) setFile(attach);      // nothing was sent: put it back so it can be retried
      setError(errorMessage(e));
    } finally { setSending(false); }
  };

  if (player && enabled === false) return null;   // live chat isn't configured: don't show a button that can't work

  const hasReply = unread > 0 && !open;

  return (
    <>
      <div className="fixed bottom-5 right-5 z-[45] flex flex-col items-end gap-2">
        <AnimatePresence>
          {hasReply && (
            <motion.button
              key="chip" initial={reduce ? false : { opacity: 0, y: 8, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 6 }}
              onClick={() => setOpen(true)} data-testid="operator-reply-chip"
              className="rounded-2xl border border-emerald-300/30 bg-[#0F1F1A] px-3.5 py-2 text-xs font-bold text-emerald-200 shadow-xl">
              New reply · tap to read
            </motion.button>
          )}
        </AnimatePresence>
        <button
          onClick={() => setOpen((v) => !v)} aria-label={hasReply ? `Live operator: ${unread} new ${unread === 1 ? "reply" : "replies"}` : "Live operator"}
          aria-expanded={open} data-testid="operator-button"
          className={cn("group relative grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] text-white shadow-[0_10px_30px_rgba(124,58,237,0.5)] ring-1 ring-white/25 transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(124,58,237,0.65)] active:scale-95",
            hasReply && !reduce && "animate-[blink_1s_ease-in-out_infinite]")}>
          {hasReply && !reduce && <span className="absolute inset-0 -z-10 animate-ping rounded-full bg-emerald-400/50" aria-hidden />}
          {hasReply && <span className={cn("absolute inset-0 rounded-full ring-[3px] ring-emerald-300", !reduce && "animate-[blink_1s_ease-in-out_infinite]")} aria-hidden />}
          {open ? <X className="h-6 w-6" /> : <Headset className={cn("h-7 w-7", hasReply && !reduce && "animate-[wiggle_1.1s_ease-in-out_infinite]")} strokeWidth={1.8} />}
          {!open && player && !hasReply && online && <span className="absolute right-0.5 top-0.5 h-3.5 w-3.5 rounded-full bg-emerald-400 ring-2 ring-[#0B0E17]" aria-hidden />}
          {hasReply && (
            <span data-testid="operator-badge" className="absolute -right-1 -top-1 grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-emerald-400 px-1 text-[11px] font-black text-slate-950 ring-2 ring-[#0B0E17]">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.section
            role="dialog" aria-label="Live operator chat" data-testid="operator-panel"
            initial={reduce ? false : { opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-24 right-3 z-[46] flex h-[min(34rem,calc(100vh-8rem))] w-[calc(100vw-1.5rem)] max-w-sm flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#0E1424] text-white shadow-[0_24px_60px_rgba(0,0,0,0.6)] sm:right-5">
            <header className="flex items-center gap-3 border-b border-white/10 bg-gradient-to-r from-[#2A1B5C] to-[#1B1F4A] px-4 py-3">
              <span className="relative grid h-10 w-10 place-items-center rounded-full bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9]">
                <Headset className="h-5 w-5" strokeWidth={1.8} />
                {player && <span className={cn("absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full ring-2 ring-[#1B1F4A]", online ? "bg-emerald-400" : "bg-slate-500")} aria-hidden />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-extrabold leading-tight">Live Operator</p>
                <p className="flex items-center gap-1.5 text-xs text-slate-300" data-testid="operator-status">
                  {!player ? "Write to our team." : online ? <><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden />Operators online</> : "Our team is away. We'll reply as soon as we're back."}
                </p>
              </div>
              <button onClick={() => setOpen(false)} aria-label="Close chat" className="rounded-full p-1.5 text-slate-300 transition hover:bg-white/10 hover:text-white"><X className="h-4 w-4" /></button>
            </header>

            {!player ? (
              <div className="grid flex-1 place-items-center p-6 text-center">
                <div>
                  <p className="font-bold">Sign in to chat with our team</p>
                  <p className="mt-1 text-sm text-slate-400">We need to know who you are so we can look into your account.</p>
                  <Link href="/login" onClick={() => setOpen(false)} className="mt-4 inline-flex h-11 items-center rounded-2xl bg-[#38bdf8] px-6 font-black text-slate-950 transition hover:bg-[#0ea5e9]">Sign in</Link>
                </div>
              </div>
            ) : (
              <>
                <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4" data-testid="operator-messages">
                  {!loaded ? <div className="grid h-full place-items-center"><Spinner className="h-5 w-5 text-sky-400" /></div> : messages.length === 0 && !typing ? (
                    <p className="mt-6 text-center text-sm text-slate-400">Hi {player.username}! Tell us how we can help and a team member will answer here.</p>
                  ) : messages.map((m) => {
                    const mine = m.sender === "player";
                    const tick = m.pending ? "sending" : m.id <= seenUpto ? "seen" : "delivered";
                    return (
                      <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
                        <div className={cn("max-w-[82%] rounded-2xl px-3.5 py-2 text-sm", mine ? "rounded-br-md bg-gradient-to-br from-[#7C3AED] to-[#5B21B6]" : "rounded-bl-md border border-white/10 bg-white/[0.06]", m.pending && "opacity-70")}>
                          {!mine && <p className="mb-0.5 text-[11px] font-bold text-emerald-300">{m.operator ?? "Operator"}</p>}
                          {m.file && m.kind === "photo" && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <a href={m.pending ? undefined : m.file} target="_blank" rel="noopener noreferrer"><img src={m.file} alt="Photo" className="mb-1 max-h-56 w-full rounded-xl object-cover" /></a>
                          )}
                          {m.file && m.kind === "video" && <video src={m.file} controls preload="metadata" className="mb-1 max-h-56 w-full rounded-xl bg-black" />}
                          {m.body && <p className="whitespace-pre-wrap break-words">{m.body}</p>}
                          <p className="mt-1 flex items-center justify-end gap-1 text-[10px] text-white/50">
                            {m.pending ? "Sending…" : hhmm(m.created_at)}
                            {mine && <span data-testid="tick" data-state={tick}><Ticks state={tick} /></span>}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                  {typing && (
                    <div className="flex justify-start" data-testid="operator-typing" aria-live="polite">
                      <div className="rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.06] px-4 py-2.5">
                        <span className="sr-only">An operator is typing</span>
                        <span className="flex items-center gap-1" aria-hidden>
                          {[0, 150, 300].map((d) => <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-slate-300" style={{ animationDelay: `${d}ms` }} />)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {error && <p role="alert" className="mx-4 mb-2 rounded-xl bg-rose-500/15 px-3 py-2 text-xs text-rose-200">{error}</p>}
                {file && (
                  <div className="mx-3 mb-2 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.05] p-2" data-testid="attachment-preview">
                    {file.kind === "photo"
                      // eslint-disable-next-line @next/next/no-img-element
                      ? <img src={file.url} alt="" className="h-14 w-14 rounded-xl object-cover" />
                      : <video src={file.url} className="h-14 w-14 rounded-xl bg-black object-cover" muted />}
                    <p className="min-w-0 flex-1 truncate text-xs text-slate-300">{file.file.name}<span className="block text-[11px] text-slate-500">{(file.file.size / 1024 / 1024).toFixed(1)} MB · add a caption below if you like</span></p>
                    <button onClick={() => setFile(null)} aria-label="Remove attachment" className="rounded-full p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white"><X className="h-4 w-4" /></button>
                  </div>
                )}
                <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex items-end gap-2 border-t border-white/10 p-3">
                  <input ref={fileInput} type="file" hidden accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm" data-testid="attachment-input"
                    onChange={(e) => { pickFile(e.target.files?.[0]); e.target.value = ""; }} />
                  <button type="button" onClick={() => fileInput.current?.click()} aria-label="Attach a photo or video" disabled={sending}
                    className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-white/10 bg-white/[0.05] text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-40">
                    <Paperclip className="h-[18px] w-[18px]" />
                  </button>
                  <textarea
                    value={text} onChange={(e) => setText(e.target.value.slice(0, MAX))} rows={1} placeholder={file ? "Add a caption…" : "Type your message…"} aria-label="Message"
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                    className="max-h-28 min-h-[2.75rem] flex-1 resize-none rounded-2xl border border-white/10 bg-white/[0.05] px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-sky-400 focus:outline-none" />
                  <button type="submit" disabled={(!text.trim() && !file) || sending} aria-label="Send message"
                    className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[#38bdf8] text-slate-950 transition hover:bg-[#0ea5e9] disabled:opacity-40">
                    {sending ? <Spinner className="h-4 w-4" /> : <Send className="h-[18px] w-[18px]" />}
                  </button>
                </form>
              </>
            )}
          </motion.section>
        )}
      </AnimatePresence>
    </>
  );
}
