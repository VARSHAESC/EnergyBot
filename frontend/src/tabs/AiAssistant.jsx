import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { Send, Mic, MicOff, Trash2, Globe, Download, Check, X } from 'lucide-react';
import { API_BASE } from '../lib/api';
import './AiAssistant.css';

export default function AiAssistant() {
    const { activeUtility } = useApp();
    const [messages,      setMessages]      = useState([]);
    const [input,         setInput]         = useState('');
    const [isTyping,      setIsTyping]      = useState(false);
    const [isStreaming,   setIsStreaming]    = useState(false);
    const [isListening,   setIsListening]   = useState(false);
    const [voiceError,    setVoiceError]    = useState('');
    const [pendingAction, setPendingAction] = useState(null);
    const messagesEndRef  = useRef(null);
    const recognitionRef  = useRef(null);
    const abortRef        = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);

    const suggestedQueries = [
        'Welche Hausanschlüsse sind älter als 30 Jahre?',
        'Welche Erneuerungen lassen sich bündeln?',
        'Welche Anschlüsse sind für Wärmepumpen ungeeignet?',
        'Identifiziere Hochrisiko-Assets.',
    ];

    /* ── Streaming chat ────────────────────────────────────────────────────── */
    const handleSend = useCallback(async (text) => {
        const query = (text || input).trim();
        if (!query || isStreaming) return;

        // Snapshot history before adding new user message
        const historySnapshot = messages.map(m => ({ role: m.role, content: m.content }));

        setMessages(prev => [...prev, { role: 'user', content: query }]);
        setInput('');
        setIsTyping(true);
        setIsStreaming(true);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const res = await fetch(`${API_BASE}/api/chat/stream`, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ query, utility: activeUtility, history: historySnapshot }),
                signal:  controller.signal,
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const reader  = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer    = '';
            let fullText  = '';
            let botAdded  = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // keep partial last line

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
                                    const copy = [...prev];
                                    copy[copy.length - 1] = { role: 'bot', content: fullText, streaming: true };
                                    return copy;
                                });
                            }
                        } else if (evt.type === 'done') {
                            const final = evt.answer !== undefined ? evt.answer : fullText;
                            setIsTyping(false);
                            if (!botAdded) {
                                setMessages(prev => [...prev, { role: 'bot', content: final, pending_action: evt.pending_action }]);
                            } else {
                                setMessages(prev => {
                                    const copy = [...prev];
                                    copy[copy.length - 1] = { role: 'bot', content: final, pending_action: evt.pending_action };
                                    return copy;
                                });
                            }
                            if (evt.pending_action) setPendingAction(evt.pending_action);
                        }
                    } catch (_) {}
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('[Chat]', err);
                setMessages(prev => [...prev, { role: 'bot', content: 'Entschuldigung, es gab einen Fehler bei der Verarbeitung Ihrer Anfrage.' }]);
            }
        } finally {
            setIsTyping(false);
            setIsStreaming(false);
            abortRef.current = null;
        }
    }, [input, messages, activeUtility, isStreaming]);

    /* ── Voice recognition ─────────────────────────────────────────────────── */
    const toggleListening = useCallback(() => {
        setVoiceError('');

        if (isListening) {
            recognitionRef.current?.stop();
            setIsListening(false);
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            setVoiceError('Ihr Browser unterstützt keine Spracherkennung. Bitte Chrome oder Edge verwenden.');
            return;
        }

        const rec = new SpeechRecognition();
        rec.lang            = 'de-DE';
        rec.continuous      = false;
        rec.interimResults  = true;
        rec.maxAlternatives = 1;

        rec.onstart = () => setIsListening(true);

        rec.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(r => r[0].transcript)
                .join('');
            setInput(transcript);

            if (event.results[event.results.length - 1].isFinal) {
                recognitionRef.current = null;
                setIsListening(false);
                // Use the captured transcript directly — avoids stale closure on `input`
                handleSend(transcript);
            }
        };

        rec.onerror = (e) => {
            if (e.error === 'not-allowed') {
                setVoiceError('Mikrofon-Zugriff verweigert. Bitte erlauben Sie den Zugriff in den Browser-Einstellungen.');
            } else if (e.error === 'no-speech') {
                setVoiceError('Keine Sprache erkannt. Bitte versuchen Sie es erneut.');
            } else {
                setVoiceError(`Sprachfehler: ${e.error}`);
            }
            setIsListening(false);
        };

        rec.onend = () => setIsListening(false);

        recognitionRef.current = rec;
        try {
            rec.start();
        } catch (e) {
            setVoiceError('Mikrofon konnte nicht gestartet werden.');
            setIsListening(false);
        }
    }, [isListening, handleSend]);

    const confirmAction = () => {
        setMessages(prev => [...prev, { role: 'bot', content: '✅ Die Änderung wurde erfolgreich im System vermerkt.' }]);
        setPendingAction(null);
    };

    const clearChat = () => {
        abortRef.current?.abort();
        setMessages([]);
        setPendingAction(null);
        setVoiceError('');
    };

    return (
        <div className="chat-container">
            <div className="chat-layout">
                <div className="chat-main">
                    <div className="chat-messages">
                        {messages.length === 0 && (
                            <div className="chat-welcome">
                                <BotIcon size={48} color="var(--color-primary)" />
                                <h3>Willkommen beim KI-Assistenten</h3>
                                <p>Ich helfe Ihnen bei der Analyse Ihres Infrastrukturbestands. Wählen Sie eine Frage rechts aus oder stellen Sie Ihre eigene.</p>
                            </div>
                        )}

                        {messages.map((msg, idx) => (
                            <div key={idx} className={`message-bubble ${msg.role}`}>
                                <div className="message-content">
                                    {msg.content}
                                    {msg.streaming && <span className="streaming-cursor" />}
                                </div>
                            </div>
                        ))}

                        {isTyping && (
                            <div className="message-bubble bot typing">
                                <div className="typing-indicator">
                                    <span /><span /><span />
                                </div>
                            </div>
                        )}

                        {pendingAction && (
                            <div className="action-card glass-card">
                                <h5>🛠️ Daten-Aktualisierung bestätigen</h5>
                                <p>Soll folgende Änderung gespeichert werden?</p>
                                <div className="action-details">
                                    {pendingAction.type === 'update_asset' && (
                                        <ul>
                                            <li><b>ID:</b> {pendingAction.args.customer_id}</li>
                                            <li><b>Feld:</b> {pendingAction.args.field_name}</li>
                                            <li><b>Neuer Wert:</b> {pendingAction.args.new_value}</li>
                                        </ul>
                                    )}
                                </div>
                                <div className="action-buttons">
                                    <button className="btn-confirm" onClick={confirmAction}><Check size={16} /> Bestätigen</button>
                                    <button className="btn-cancel-action" onClick={() => setPendingAction(null)}><X size={16} /> Abbrechen</button>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    <div className="chat-input-area">
                        <button className="btn-tool" onClick={clearChat} title="Chat löschen">
                            <Trash2 size={20} />
                        </button>
                        <div className={`input-wrapper ${isListening ? 'input-wrapper--listening' : ''}`}>
                            <input
                                type="text"
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                                placeholder={isListening ? '🎙️ Sprechen Sie jetzt…' : 'Stellen Sie eine Frage…'}
                                disabled={isStreaming}
                            />
                            <button
                                className="btn-send"
                                onClick={() => handleSend()}
                                disabled={isStreaming || !input.trim()}
                            >
                                <Send size={20} />
                            </button>
                        </div>
                        <button
                            className={`btn-mic ${isListening ? 'btn-mic--active' : ''}`}
                            onClick={toggleListening}
                            title={isListening ? 'Aufnahme stoppen' : 'Spracheingabe starten'}
                        >
                            {isListening ? <MicOff size={20} /> : <Mic size={20} />}
                        </button>
                    </div>

                    {voiceError && (
                        <div className="voice-error">
                            {voiceError}
                            <button onClick={() => setVoiceError('')}><X size={12} /></button>
                        </div>
                    )}
                </div>

                <div className="chat-sidebar">
                    <h4>Strategische Analyse-Vorgaben</h4>
                    <div className="suggestions-list">
                        {suggestedQueries.map((q, i) => (
                            <button key={i} className="suggestion-btn" onClick={() => handleSend(q)}>
                                {q}
                            </button>
                        ))}
                    </div>

                    <div className="chat-status-card glass-card">
                        <div className="status-item">
                            <Globe size={16} />
                            <span>Systemdaten: Online</span>
                        </div>
                        <div className="status-item">
                            <Download size={16} />
                            <span>Export-Modul: Bereit</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function BotIcon({ size, color }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
            fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 8V4H8"/>
            <rect width="16" height="12" x="4" y="8" rx="2"/>
            <path d="M2 14h2"/><path d="M20 14h2"/>
            <path d="M15 13v2"/><path d="M9 13v2"/>
        </svg>
    );
}
