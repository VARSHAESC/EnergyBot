import { useState, useRef, useCallback, useEffect, useMemo, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { motion } from 'framer-motion';
import { useApp } from '../context/AppContext';
import { useTheme } from '../context/ThemeContext';
import { useLanguage } from '../context/LanguageContext';
import { API_BASE } from '../lib/api';
import MiniBotPortal from '../components/3d/MiniBotPortal';
import {
  Send, Mic, MicOff, Trash2, Check, X,
  Bot, Zap, Globe, Download, Activity,
} from 'lucide-react';
import './AiIntelligencePage.css';

/* ─────────────────────────────────────────────────────────────────────────────
   Full-screen background: floating nodes + glowing energy wires
───────────────────────────────────────────────────────────────────────────── */
function EnergyBackground({ isDark }) {
  const meshRefs = useRef([]);

  const nodes = useMemo(() => Array.from({ length: 22 }, (_, i) => {
    const s = i + 1;
    return {
      x: ((s * 7) % 19) / 19 * 20 - 10,
      y: ((s * 5) % 11) / 11 * 10 - 5,
      z: -(((s * 3) % 7) / 7 * 5 + 1),
      r: 0.04 + (s % 5) * 0.016,
      speed: 0.3 + (s % 6) * 0.14,
      phase: (s * 0.618) % (Math.PI * 2),
      teal: s % 3 !== 0,
    };
  }), []);

  const wires = useMemo(() => {
    const pairs = [];
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        const dx = nodes[a].x - nodes[b].x;
        const dy = nodes[a].y - nodes[b].y;
        const dz = nodes[a].z - nodes[b].z;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (d < 6) pairs.push({ a, b, d });
      }
    }
    return pairs.slice(0, 28);
  }, [nodes]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    meshRefs.current.forEach((m, i) => {
      if (!m) return;
      const n = nodes[i];
      m.position.y = n.y + Math.sin(t * n.speed + n.phase) * 0.28;
      m.material.emissiveIntensity = 0.7 + 0.45 * Math.sin(t * n.speed * 1.6 + n.phase);
    });
  });

  return (
    <>
      {nodes.map((n, i) => (
        <mesh key={`n${i}`} ref={el => { meshRefs.current[i] = el; }} position={[n.x, n.y, n.z]}>
          <sphereGeometry args={[n.r, 8, 8]} />
          <meshStandardMaterial
            color={n.teal ? '#00d4d4' : '#0066cc'}
            emissive={n.teal ? '#00d4d4' : '#0066cc'}
            emissiveIntensity={0.9}
          />
        </mesh>
      ))}

      {wires.map(({ a, b, d }, wi) => (
        <Line
          key={`w${wi}`}
          points={[
            [nodes[a].x, nodes[a].y, nodes[a].z],
            [nodes[b].x, nodes[b].y, nodes[b].z],
          ]}
          color={nodes[a].teal ? '#00d4d4' : '#0055bb'}
          lineWidth={isDark ? 0.9 : 0.5}
          transparent
          opacity={Math.max(0.05, (6 - d) / 6 * 0.22)}
        />
      ))}
    </>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Status badge
───────────────────────────────────────────────────────────────────────────── */
const STATUS_META = {
  idle: { de: 'Bereit', en: 'Ready', key: 'common.ready', cls: 'badge--idle' },
  thinking: { de: 'Analysiert…', en: 'Thinking…', key: 'common.thinking', cls: 'badge--thinking' },
  success: { de: 'Fertig', en: 'Done', key: 'common.done', cls: 'badge--success' },
};

function StatusBadge({ status, t }) {
  const m = STATUS_META[status] ?? STATUS_META.idle;
  return (
    <span className={`robot-badge ${m.cls}`}>
      <span className="badge-dot" />
      {t(m.key)}
    </span>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Main Page
───────────────────────────────────────────────────────────────────────────── */
export default function AiIntelligencePage() {
  const { activeUtility } = useApp();
  const { theme } = useTheme();
  const { lang, t } = useLanguage();
  const isDark = theme === 'dark';

  /* Robot state */
  const [robotStatus, setRobotStatus] = useState('idle');
  const successTimerRef = useRef(null);

  const triggerSuccess = useCallback(() => {
    clearTimeout(successTimerRef.current);
    setRobotStatus('success');
    successTimerRef.current = setTimeout(() => setRobotStatus('idle'), 2800);
  }, []);

  useEffect(() => () => clearTimeout(successTimerRef.current), []);

  /* Chat state */
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [pendingAction, setPendingAction] = useState(null);

  const messagesEndRef = useRef(null);
  const recognitionRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const quickReplies = lang === 'en' ? [
    'Assets older than 40 years',
    'Which renewals are overdue?',
    'Bundle renewals by street',
    'Missing documents?',
    'What patterns stand out?',
    'Heat pump suitability',
    'Failure risk correlation',
  ] : [
    'Anschlüsse älter als 40 Jahre',
    'Welche Erneuerungen sind überfällig?',
    'Erneuerungen nach Straßenzug bündeln',
    'Fehlende Dokumente prüfen',
    'Welche Muster fallen auf?',
    'Eignung für Wärmepumpen',
    'Zusammenhang Baujahr & Störung',
  ];

  /* ── Streaming chat ── */
  const handleSend = useCallback(async (text) => {
    const query = (text ?? input).trim();
    if (!query || isStreaming) return;

    const historySnapshot = messages.map(m => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, { role: 'user', content: query }]);
    setInput('');
    setIsTyping(true);
    setIsStreaming(true);
    setRobotStatus('thinking');

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, utility: activeUtility, history: historySnapshot }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';
      let botAdded = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const evt = JSON.parse(raw);
            if (evt.type === 'token' && evt.token) {
              fullText += evt.token;
              setIsTyping(false);
              if (!botAdded) {
                botAdded = true;
                setMessages(prev => [...prev, { role: 'bot', content: fullText, streaming: true }]);
              } else {
                setMessages(prev => {
                  const c = [...prev];
                  c[c.length - 1] = { role: 'bot', content: fullText, streaming: true };
                  return c;
                });
              }
            } else if (evt.type === 'done') {
              const final = evt.answer !== undefined ? evt.answer : fullText;
              setIsTyping(false);
              if (!botAdded) {
                setMessages(prev => [...prev, { role: 'bot', content: final, pending_action: evt.pending_action }]);
              } else {
                setMessages(prev => {
                  const c = [...prev];
                  c[c.length - 1] = { role: 'bot', content: final, pending_action: evt.pending_action };
                  return c;
                });
              }
              if (evt.pending_action) setPendingAction(evt.pending_action);
              triggerSuccess();
            }
          } catch (_) { }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setMessages(prev => [...prev, {
          role: 'bot',
          content: t('common.errorOccurred') || (lang === 'en'
            ? 'Sorry, an error occurred while processing your request.'
            : 'Entschuldigung, es gab einen Fehler bei der Verarbeitung Ihrer Anfrage.'),
        }]);
        setRobotStatus('idle');
      }
    } finally {
      setIsTyping(false);
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [input, messages, activeUtility, isStreaming, lang, triggerSuccess]);

  /* ── Voice recognition ── */
  const toggleListening = useCallback(() => {
    setVoiceError('');
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      setVoiceError(t('common.unsupportedSpeech') || (lang === 'en'
        ? 'Speech recognition not supported. Use Chrome or Edge.'
        : 'Spracherkennung nicht unterstützt. Bitte Chrome oder Edge verwenden.'));
      return;
    }
    const rec = new SpeechRec();
    rec.lang = lang === 'en' ? 'en-US' : 'de-DE';
    rec.continuous = false;
    rec.interimResults = true;
    rec.onstart = () => setIsListening(true);
    rec.onresult = (e) => {
      const t = Array.from(e.results).map(r => r[0].transcript).join('');
      setInput(t);
      if (e.results[e.results.length - 1].isFinal) {
        recognitionRef.current = null;
        setIsListening(false);
        handleSend(t);
      }
    };
    rec.onerror = (e) => { setVoiceError(e.error); setIsListening(false); };
    rec.onend = () => setIsListening(false);
    recognitionRef.current = rec;
    try { rec.start(); } catch (_) { setVoiceError('Mic error'); setIsListening(false); }
  }, [isListening, lang, handleSend]);

  const confirmAction = () => {
    setMessages(prev => [...prev, { role: 'bot', content: '✅ Änderung erfolgreich gespeichert.' }]);
    setPendingAction(null);
  };

  const clearChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setPendingAction(null);
    setVoiceError('');
    setRobotStatus('idle');
  };

  return (
    <div className="aie-page">

      {/* ── Full-screen background canvas ── */}
      <div className="aie-bg" aria-hidden="true">
        <Canvas
          camera={{ position: [0, 0, 7], fov: 88 }}
          gl={{ antialias: false, alpha: false }}
          dpr={[0.8, 1]}
        >
          <color attach="background" args={[isDark ? '#050a12' : '#ddeaf8']} />
          <ambientLight intensity={isDark ? 0.15 : 0.5} />
          <Suspense fallback={null}>
            <EnergyBackground isDark={isDark} />
          </Suspense>
          <EffectComposer>
            <Bloom intensity={isDark ? 1.8 : 0.4} luminanceThreshold={0.2} luminanceSmoothing={0.9} />
          </EffectComposer>
        </Canvas>
      </div>

      {/* ── Centered chat window ── */}
      <motion.div
        className="aie-window"
        initial={{ opacity: 0, y: 28, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
      >

        {/* Header */}
        <div className="aie-header">
          <div className="aie-header-bot-icon">
            <Bot size={16} />
          </div>
          <div className="aie-header-info">
            <span className="aie-title">{t('nav.aiIntelligence')}</span>
            <StatusBadge status={robotStatus} t={t} />
          </div>
          <div className="aie-header-actions">
            <button className="btn-icon-sm" onClick={clearChat}
              title={t('common.clearChat')}>
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {/* Quick-reply tag strip */}
        <div className="aie-quick-strip-container">
          <div className="aie-quick-strip">
            {quickReplies.map((q, i) => (
              <button
                key={i}
                className="aie-quick-tag"
                onClick={() => handleSend(q)}
                disabled={isStreaming}
              >
                <Zap size={10} />
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="aie-messages">
          {messages.length === 0 && (
            <div className="aie-welcome">
              <p className="aie-welcome-hint">
                {t('common.welcomeHint')}
              </p>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isLastBot = msg.role === 'bot' && idx === messages.length - 1;
            return (
              <motion.div
                key={idx}
                className={`aie-bubble ${msg.role}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22 }}
              >
                {msg.role === 'bot' && (
                  <div className={`aie-bot-avatar ${isLastBot ? 'latest' : ''}`}>
                    <Bot size={13} />
                  </div>
                )}
                <div className="aie-bubble-text">
                  {msg.content}
                  {msg.streaming && <span className="streaming-cursor" />}
                </div>
              </motion.div>
            );
          })}

          {isTyping && (
            <div className="aie-bubble bot typing">
              <div className="aie-bot-avatar latest"><Bot size={13} /></div>
              <div className="typing-dots">
                <span /><span /><span />
              </div>
            </div>
          )}

          {pendingAction && (
            <div className="aie-action-card glass-card">
              <h5>🛠️ {t('common.confirmDataUpdate')}</h5>
              <p>{t('common.saveChange')}</p>
              {pendingAction.type === 'update_asset' && (
                <ul className="aie-action-list">
                  <li><b>ID:</b> {pendingAction.args.customer_id}</li>
                  <li><b>{t('common.field')}:</b> {pendingAction.args.field_name}</li>
                  <li><b>{t('common.value')}:</b> {pendingAction.args.new_value}</li>
                </ul>
              )}
              <div className="aie-action-btns">
                <button className="btn-confirm-ai" onClick={confirmAction}>
                  <Check size={13} /> {t('common.confirm')}
                </button>
                <button className="btn-cancel-ai" onClick={() => setPendingAction(null)}>
                  <X size={13} /> {t('common.cancel')}
                </button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Voice error */}
        {voiceError && (
          <div className="aie-voice-error">
            <Activity size={12} />
            <span>{voiceError}</span>
            <button onClick={() => setVoiceError('')}><X size={11} /></button>
          </div>
        )}

        {/* Input bar */}
        <div className="aie-input-row">
          <div className={`aie-input-wrap ${isListening ? 'listening' : ''}`}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={
                isListening
                  ? t('common.speakNow')
                  : t('common.askAi')
              }
              disabled={isStreaming}
            />
            <button
              className="btn-send-ai"
              onClick={() => handleSend()}
              disabled={isStreaming || !input.trim()}
            >
              <Send size={16} />
            </button>
          </div>
          <button
            className={`btn-mic-ai ${isListening ? 'active' : ''}`}
            onClick={toggleListening}
          >
            {isListening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
        </div>

        {/* Footer */}
        <div className="aie-footer">
          <Globe size={11} />
          <span>{t('common.systemOnline')}</span>
          <span className="aie-sep">·</span>
          <Download size={11} />
          <span>{t('common.exportReady')}</span>
          <span className="aie-sep">·</span>
          <span className="aie-utility-tag">{activeUtility}</span>
        </div>
      </motion.div>

      {/* ── Robot corner overlay — bottom-right, above input bar ── */}
      <div className="aie-robot-corner" aria-hidden="true">
        <MiniBotPortal status={robotStatus} size={112} />
      </div>
    </div>
  );
}
