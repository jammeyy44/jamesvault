"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Gift, Mic, Send, Volume2, VolumeX, X } from "lucide-react";
import { OPEN_WALLET_EVENT, deviceId, notifyWalletChanged } from "./wallet-panel";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; text: string };
type Proposal =
  | { type: "deposit"; method_id: string; method_name: string; pay: string; credit: string; summary: string }
  | { type: "add_cash"; slug: string; game: string; amount: string; source: "wallet" | "bonus"; bonus: string; bonus_percent: number; total: string; summary: string };
type Action = { type: "navigate"; path: string } | { type: "open_wallet" };
type Reply = { reply: string; proposals: Proposal[]; actions: Action[] };

const money = (v: string | number) => `$${Number(v).toFixed(2)}`;
const STORE_SPEAK = "jv-voice-speak";
const STORE_LANG = "jv-voice-lang";
const LANGS: [string, string][] = [["en-US", "English (US)"], ["en-IN", "English (India)"], ["en-GB", "English (UK)"], ["en-AU", "English (AU)"]];
const STOP_WORDS = /^(stop|stop listening|that'?s all|that is all|goodbye|good bye|bye|bye bye|thanks bye|thank you bye|cancel listening)[.!\s]*$/i;

function speechRecognition(): any | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

/** Mic assistant: speak or type, it answers aloud and proposes actions. Money only moves when the player taps Confirm. */
export function VoiceAssistant() {
  const { player } = useAuth();
  const router = useRouter();
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [speakOn, setSpeakOn] = useState(true);
  const [text, setText] = useState("");
  const [heard, setHeard] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState(false);
  const [handsFree, setHandsFree] = useState(false);
  const [lang, setLang] = useState("en-US");
  const handsFreeRef = useRef(false);
  const langRef = useRef("en-US");
  const retriesRef = useRef(0);
  const proposalRef = useRef<Proposal | null>(null);
  const recRef = useRef<any>(null);
  const keyRef = useRef<string>("");
  const msgsRef = useRef<Msg[]>([]);
  const sendRef = useRef<(t: string) => Promise<void>>(async () => {});
  const endRef = useRef<HTMLDivElement>(null);
  const supported = typeof window !== "undefined" && !!speechRecognition();

  msgsRef.current = msgs;
  proposalRef.current = proposal;
  handsFreeRef.current = handsFree;
  langRef.current = lang;
  useEffect(() => {
    try { setSpeakOn(localStorage.getItem(STORE_SPEAK) !== "0"); } catch { /* ignore */ }
    let l = "en-US";
    try { l = localStorage.getItem(STORE_LANG) || ""; } catch { /* ignore */ }
    if (!LANGS.some(([c]) => c === l)) l = LANGS.find(([c]) => c === navigator.language)?.[0] ?? "en-US";   // follow the phone's English (e.g. India) by default
    setLang(l);
  }, []);
  useEffect(() => {
    if (!player) { setEnabled(false); return; }
    api<{ enabled: boolean }>("/assistant/status").then((r) => setEnabled(r.enabled)).catch(() => setEnabled(false));
  }, [player]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, proposal, thinking]);
  useEffect(() => () => { try { recRef.current?.abort(); window.speechSynthesis?.cancel(); } catch { /* ignore */ } }, []);

  const stopSpeaking = () => { try { window.speechSynthesis?.cancel(); } catch { /* ignore */ } setSpeaking(false); };

  const speak = useCallback((line: string, then?: () => void) => {
    if (!speakOn || typeof window === "undefined" || !window.speechSynthesis) { then?.(); return; }
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(line.replace(/\s+/g, " "));
      const voices = window.speechSynthesis.getVoices();
      u.voice = voices.find((v) => /^en/i.test(v.lang) && /natural|google|samantha|aria|jenny/i.test(v.name)) ?? voices.find((v) => /^en/i.test(v.lang)) ?? null;
      u.lang = u.voice?.lang ?? "en-US";
      u.rate = 1.04;
      let done = false;
      const finish = () => { if (done) return; done = true; setSpeaking(false); then?.(); };
      u.onstart = () => setSpeaking(true);
      u.onend = finish;
      u.onerror = finish;
      window.speechSynthesis.speak(u);
      setTimeout(finish, 2500 + line.length * 90);   // some mobile browsers never report the end of speech
    } catch { then?.(); }
  }, [speakOn]);

  const add = (role: Msg["role"], t: string) => setMsgs((m) => [...m, { role, text: t }]);

  const runAction = useCallback((a: Action) => {
    if (a.type === "open_wallet") window.dispatchEvent(new CustomEvent(OPEN_WALLET_EVENT));
    else router.push(a.path);
  }, [router]);

  const stopAll = useCallback(() => {
    handsFreeRef.current = false; setHandsFree(false); retriesRef.current = 0;
    try { recRef.current?.abort(); } catch { /* ignore */ }
    stopSpeaking(); setListening(false); setHeard("");
  }, []);

  const startListening = useCallback(() => {
    const SR = speechRecognition();
    if (!SR) { add("assistant", "Your browser can't listen. Please type instead."); return; }
    stopSpeaking();
    try { recRef.current?.abort(); } catch { /* ignore */ }
    const rec = new SR();
    rec.lang = langRef.current;
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "";
    let failed = false;
    rec.onstart = () => { setListening(true); setHeard(""); };
    rec.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
      }
      setHeard((finalText + interim).trim());
    };
    rec.onerror = (e: any) => {
      setListening(false);
      failed = true;
      if (e.error === "no-speech" && handsFreeRef.current) {   // silence while hands-free: wait a little, then give up politely
        if (retriesRef.current < 2) { retriesRef.current += 1; setTimeout(() => { if (handsFreeRef.current && !proposalRef.current) startListening(); }, 300); }
        else { stopAll(); add("assistant", "I'll stop listening now. Tap the mic whenever you're ready."); }
        return;
      }
      if (e.error !== "aborted" && e.error !== "no-speech") { handsFreeRef.current = false; setHandsFree(false); }
      const why: Record<string, string> = {
        "not-allowed": "The microphone is blocked. Allow it for this site in your browser settings, or type instead.",
        "service-not-allowed": "This browser doesn't allow voice input here. Try Chrome or Safari, or type instead.",
        "network": "Voice recognition couldn't reach its speech service. Check your connection, or note that Brave and some privacy browsers block it. Try Chrome, or type instead.",
        "audio-capture": "I can't find a working microphone on this device. Check it is plugged in and not used by another app, or type instead.",
        "language-not-supported": "Voice recognition doesn't support this language setting. Type instead.",
        "no-speech": "I didn't hear anything. Tap the mic and speak right after it turns red.",
      };
      if (e.error !== "aborted") add("assistant", why[e.error] ?? `Voice input stopped (${e.error ?? "unknown"}). Try again or type.`);
    };
    rec.onend = () => {
      setListening(false);
      const said = finalText.trim();
      setHeard("");
      if (said.length > 1) { retriesRef.current = 0; void sendRef.current(said); }
      else if (!failed && handsFreeRef.current && !proposalRef.current) {   // ended without hearing anything: listen again a couple of times
        if (retriesRef.current < 2) { retriesRef.current += 1; setTimeout(() => { if (handsFreeRef.current && !proposalRef.current) startListening(); }, 300); }
        else { stopAll(); add("assistant", "I'll stop listening now. Tap the mic whenever you're ready."); }
      }
    };
    recRef.current = rec;
    try { rec.start(); } catch { setListening(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const keepListening = () => { if (handsFreeRef.current && !proposalRef.current && supported) startListening(); };

  const send = async (said: string) => {
    const clean = said.trim().slice(0, 300);
    if (!clean || thinking) return;
    if (STOP_WORDS.test(clean)) {
      setMsgs((m) => [...m, { role: "user", text: clean }]);
      const line = "Okay, I'll stop listening. Tap the mic anytime.";
      stopAll(); add("assistant", line); speak(line);
      return;
    }
    const next: Msg[] = [...msgsRef.current, { role: "user", text: clean }];
    setMsgs(next);
    setText("");
    setProposal(null);
    setThinking(true);
    try {
      const r = await api<Reply>("/assistant/chat", { method: "POST", body: { messages: next.slice(-8).map((m) => ({ role: m.role, content: m.text })) } });
      add("assistant", r.reply);
      if (r.proposals[0]) { keyRef.current = crypto.randomUUID(); proposalRef.current = r.proposals[0]; setProposal(r.proposals[0]); }
      r.actions.forEach(runAction);
      speak(r.reply, keepListening);
    } catch (e) {
      const m = errorMessage(e);
      add("assistant", m);
      speak(m, keepListening);
    } finally { setThinking(false); }
  };

  sendRef.current = send;

  const confirm = async () => {
    if (!proposal || busy) return;
    setBusy(true);
    try {
      if (proposal.type === "deposit") {
        const o = await api<{ payment_url?: string | null; status: string; amount: string }>("/wallet/deposits", {
          method: "POST", body: { method_id: proposal.method_id, amount: proposal.pay, idempotency_key: keyRef.current, device_fingerprint: deviceId() },
        });
        setProposal(null);
        if (o.payment_url) {
          const line = "Taking you to the payment page now. Come back here when you're done.";
          add("assistant", line); stopAll(); speak(line, () => { window.location.href = o.payment_url as string; });
          setTimeout(() => { window.location.href = o.payment_url as string; }, 2500);
        } else {
          const line = o.status === "paid" ? `Done. ${money(o.amount)} is in your wallet.` : "Your deposit is created. The wallet updates when the payment is confirmed.";
          add("assistant", line); speak(line, keepListening); notifyWalletChanged();
        }
      } else {
        const r = await api<{ status: string; amount: string; bonus?: string; note?: string | null }>(`/games/${proposal.slug}/cash`, {
          method: "POST", body: { amount: proposal.amount, source: proposal.source, idempotency_key: keyRef.current },
        });
        setProposal(null);
        const extra = Number(r.bonus ?? 0) > 0 ? ` plus a ${money(r.bonus!)} bonus` : "";
        const line = r.status === "completed" ? `Done. ${money(r.amount)}${extra} is now in ${proposal.game}.`
          : r.status === "failed" ? `${proposal.game} couldn't take the cash, so nothing was charged.`
          : "Your funds are held while we confirm the credit with the game. Nothing is lost.";
        add("assistant", line); speak(line, keepListening); notifyWalletChanged();
      }
    } catch (e) {
      const m = errorMessage(e);
      setProposal(null); proposalRef.current = null; add("assistant", m); speak(m, keepListening);
    } finally { setBusy(false); }
  };

  const cancel = () => { setProposal(null); proposalRef.current = null; const line = "Okay, cancelled. Nothing was changed."; add("assistant", line); speak(line, keepListening); };
  const toggleSpeak = () => { const n = !speakOn; setSpeakOn(n); if (!n) stopSpeaking(); try { localStorage.setItem(STORE_SPEAK, n ? "1" : "0"); } catch { /* ignore */ } };
  const toggleOpen = () => { if (open) stopAll(); setOpen(!open); };
  const micTap = () => {
    if (listening || handsFree) { stopAll(); return; }
    handsFreeRef.current = true; retriesRef.current = 0; setHandsFree(true); startListening();   // one tap starts a hands-free conversation
  };
  const pickLang = (l: string) => { setLang(l); langRef.current = l; try { localStorage.setItem(STORE_LANG, l); } catch { /* ignore */ } };

  if (!player || !enabled) return null;
  const hint = listening ? "Listening… just talk" : thinking ? "Thinking…" : speaking ? "Speaking… tap a message to stop" : handsFree ? "Hands-free: I'll listen again" : "Tap the mic and talk";

  return (
    <>
      {open && (
        <section role="dialog" aria-label="Voice assistant" data-testid="voice-panel"
          className="fixed bottom-24 left-3 z-[48] flex h-[min(34rem,calc(100vh-8rem))] w-[calc(100vw-1.5rem)] max-w-sm flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#0E1424] text-white shadow-[0_24px_60px_rgba(0,0,0,0.6)] sm:left-5">
          <header className="flex items-center gap-3 border-b border-white/10 bg-gradient-to-r from-[#3b1a5c] to-[#1b2352] px-4 py-3">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-[#e879f9] to-[#6366f1]"><Mic className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1"><p className="text-sm font-extrabold leading-tight">Voice assistant</p><p className="text-[11px] text-slate-300">{hint}</p></div>
            <select value={lang} onChange={(e) => pickLang(e.target.value)} aria-label="Speech language" title="Speech language: pick the accent that matches how you speak"
              className="h-8 max-w-[5.5rem] rounded-lg border border-white/15 bg-white/10 px-1.5 text-[11px] font-semibold text-slate-100 outline-none">
              {LANGS.map(([c, n]) => <option key={c} value={c} className="bg-[#0E1424]">{n}</option>)}
            </select>
            <button onClick={toggleSpeak} aria-label={speakOn ? "Mute voice replies" : "Turn voice replies on"} className="grid h-8 w-8 place-items-center rounded-full text-slate-300 hover:bg-white/10">{speakOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}</button>
            <button onClick={toggleOpen} aria-label="Close assistant" className="grid h-8 w-8 place-items-center rounded-full text-slate-300 hover:bg-white/10"><X className="h-4 w-4" /></button>
          </header>

          <div className="flex-1 space-y-2.5 overflow-y-auto px-3.5 py-3" onClick={stopSpeaking}>
            {msgs.length === 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3.5 text-[13px] leading-relaxed text-slate-300">
                Tap the mic and ask, for example:
                <ul className="mt-1.5 space-y-1 text-slate-200">
                  <li>“What&apos;s my balance?”</li><li>“I want to deposit twenty five dollars on card”</li><li>“Load ten dollars in Game Vault”</li><li>“What can I cash out on Game Vault?”</li><li>“Take me to the bonus zone”</li>
                </ul>
                <p className="mt-2 text-[11px] text-slate-500">Tap the mic once and just keep talking; say “stop” when you're done. I always ask you to confirm before any money moves. If I mishear you, pick your accent at the top.</p>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn("max-w-[85%] rounded-2xl px-3.5 py-2 text-sm", m.role === "user" ? "rounded-br-md bg-gradient-to-br from-[#7C3AED] to-[#4F46E5]" : "rounded-bl-md border border-white/10 bg-white/[0.06]")}>{m.text}</div>
              </div>
            ))}
            {heard && <div className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-white/10 px-3.5 py-2 text-sm italic text-slate-300">{heard}</div></div>}
            {thinking && <div className="flex justify-start"><div className="rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.06] px-3.5 py-2.5"><span className="proc-dots" aria-label="Thinking"><i /><i /><i /></span></div></div>}

            {proposal && (
              <div data-testid="voice-confirm" className="rounded-2xl border border-[#ffd966]/35 bg-gradient-to-br from-[#ffd966]/15 to-transparent p-3.5">
                <p className="flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-wider text-[#ffd966]"><Gift className="h-3.5 w-3.5" />Please confirm</p>
                <p className="mt-1.5 text-sm font-semibold text-white">{proposal.summary}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button onClick={confirm} disabled={busy} data-testid="voice-confirm-yes" className="inline-flex h-11 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-[#34d399] to-[#10b981] text-sm font-black text-slate-950 transition hover:brightness-110 active:scale-95 disabled:opacity-60">
                    <Check className="h-4 w-4" />{busy ? "Working…" : "Confirm"}
                  </button>
                  <button onClick={cancel} disabled={busy} className="h-11 rounded-xl border border-white/15 text-sm font-bold text-slate-200 transition hover:bg-white/10">Cancel</button>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form className="flex items-center gap-2 border-t border-white/10 bg-[#0B101D] p-2.5" onSubmit={(e) => { e.preventDefault(); void send(text); }}>
            <button type="button" onClick={micTap} aria-label={listening || handsFree ? "Stop listening" : "Start listening"} data-testid="voice-mic"
              disabled={!supported || thinking}
              className={cn("relative grid h-12 w-12 shrink-0 place-items-center rounded-full text-white transition disabled:opacity-40", listening ? "bg-rose-500" : handsFree ? "bg-emerald-500" : "bg-gradient-to-br from-[#e879f9] to-[#6366f1] hover:brightness-110")}>
              {listening && <span className="absolute inset-0 animate-ping rounded-full bg-rose-400/50" aria-hidden />}
              <Mic className="relative h-5 w-5" />
            </button>
            <input value={text} onChange={(e) => setText(e.target.value)} maxLength={300} placeholder={supported ? "…or type here" : "Type here (voice isn't supported in this browser)"} aria-label="Type a message"
              className="h-11 min-w-0 flex-1 rounded-2xl border border-white/10 bg-white/[0.06] px-3.5 text-sm outline-none placeholder:text-white/35 focus:border-fuchsia-400/60" />
            <button type="submit" disabled={!text.trim() || thinking} aria-label="Send" className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[#38bdf8] text-slate-950 transition hover:bg-[#0ea5e9] disabled:opacity-40"><Send className="h-4 w-4" /></button>
          </form>
        </section>
      )}

      <button onClick={toggleOpen} aria-label={open ? "Close voice assistant" : "Open voice assistant"} data-testid="voice-launcher"
        className={cn("fixed bottom-4 left-3 z-[48] grid h-14 w-14 place-items-center rounded-full text-white ring-1 ring-white/25 transition hover:-translate-y-0.5 active:scale-95 sm:left-5",
          "bg-gradient-to-br from-[#e879f9] via-[#a855f7] to-[#6366f1] shadow-[0_10px_30px_rgba(168,85,247,0.5)]")}>
        {(listening || speaking) && <span className="absolute inset-0 animate-ping rounded-full bg-fuchsia-400/40" aria-hidden />}
        {open ? <X className="relative h-6 w-6" /> : <Mic className="relative h-6 w-6" strokeWidth={1.8} />}
      </button>
    </>
  );
}
