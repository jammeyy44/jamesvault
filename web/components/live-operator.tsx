"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Headset, Send, X } from "lucide-react";
import { Spinner } from "./ui/bits";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Msg = { id: number; sender: "player" | "operator"; body: string; operator: string | null; created_at: string; pending?: boolean };
type ChatState = { enabled: boolean; messages: Msg[]; unread: number };

const MAX = 1000;
const POLL_OPEN_MS = 4000;
const POLL_CLOSED_MS = 20000;
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Floating "Live Operator" button + chat panel. The team answers from a Telegram group; replies appear here. */
export function LiveOperator() {
  const { player } = useAuth();
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [unread, setUnread] = useState(0);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const lastId = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
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
      setLoaded(true);
      if (openRef.current) { if (s.unread > 0) markRead(); } else setUnread(s.unread);
    } catch { /* offline or signed out: try again on the next tick */ }
  }, [merge, markRead]);

  // Reset when the signed-in player changes.
  useEffect(() => {
    lastId.current = 0; setMessages([]); setUnread(0); setLoaded(false); setEnabled(player ? null : false);
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
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: reduce ? "auto" : "smooth" }); }, [messages, open, reduce]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true); setError(null);
    const tempId = -Date.now();
    setMessages((cur) => [...cur, { id: tempId, sender: "player", body, operator: null, created_at: new Date().toISOString(), pending: true }]);
    setText("");
    try {
      const m = await api<Msg>("/chat/messages", { method: "POST", body: { text: body } });
      setMessages((cur) => cur.filter((x) => x.id !== tempId));
      merge([m]);
    } catch (e) {
      setMessages((cur) => cur.filter((x) => x.id !== tempId));
      setText(body);                      // nothing was sent: put the text back so it can be retried
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
              Support replied · tap to read
            </motion.button>
          )}
        </AnimatePresence>
        <button
          onClick={() => setOpen((v) => !v)} aria-label={hasReply ? `Live operator: ${unread} new ${unread === 1 ? "reply" : "replies"}` : "Live operator"}
          aria-expanded={open} data-testid="operator-button"
          className="group relative grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] text-white shadow-[0_10px_30px_rgba(124,58,237,0.5)] ring-1 ring-white/25 transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(124,58,237,0.65)] active:scale-95">
          {hasReply && !reduce && <span className="absolute inset-0 -z-10 animate-ping rounded-full bg-emerald-400/50" aria-hidden />}
          {hasReply && <span className="absolute inset-0 rounded-full ring-2 ring-emerald-300/80" aria-hidden />}
          {open ? <X className="h-6 w-6" /> : <Headset className={cn("h-7 w-7", hasReply && !reduce && "animate-[wiggle_1.1s_ease-in-out_infinite]")} strokeWidth={1.8} />}
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
              <span className="grid h-10 w-10 place-items-center rounded-full bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9]"><Headset className="h-5 w-5" strokeWidth={1.8} /></span>
              <div className="min-w-0 flex-1">
                <p className="font-extrabold leading-tight">Live Operator</p>
                <p className="text-xs text-slate-300">Write to our team. Replies appear here.</p>
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
                  {!loaded ? <div className="grid h-full place-items-center"><Spinner className="h-5 w-5 text-sky-400" /></div> : messages.length === 0 ? (
                    <p className="mt-6 text-center text-sm text-slate-400">Hi {player.username}! Tell us how we can help and a team member will answer here.</p>
                  ) : messages.map((m) => (
                    <div key={m.id} className={cn("flex", m.sender === "player" ? "justify-end" : "justify-start")}>
                      <div className={cn("max-w-[82%] rounded-2xl px-3.5 py-2 text-sm", m.sender === "player" ? "rounded-br-md bg-gradient-to-br from-[#7C3AED] to-[#5B21B6]" : "rounded-bl-md border border-white/10 bg-white/[0.06]", m.pending && "opacity-60")}>
                        {m.sender === "operator" && <p className="mb-0.5 text-[11px] font-bold text-emerald-300">{m.operator ?? "Support"}</p>}
                        <p className="whitespace-pre-wrap break-words">{m.body}</p>
                        <p className="mt-1 text-right text-[10px] text-white/50">{m.pending ? "Sending…" : hhmm(m.created_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {error && <p role="alert" className="mx-4 mb-2 rounded-xl bg-rose-500/15 px-3 py-2 text-xs text-rose-200">{error}</p>}
                <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex items-end gap-2 border-t border-white/10 p-3">
                  <textarea
                    value={text} onChange={(e) => setText(e.target.value.slice(0, MAX))} rows={1} placeholder="Type your message…" aria-label="Message"
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                    className="max-h-28 min-h-[2.75rem] flex-1 resize-none rounded-2xl border border-white/10 bg-white/[0.05] px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-sky-400 focus:outline-none" />
                  <button type="submit" disabled={!text.trim() || sending} aria-label="Send message"
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
