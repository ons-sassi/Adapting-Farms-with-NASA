import { useEffect, useRef, useState } from 'react'
import { Bot, Mic, Send, ThumbsDown, ThumbsUp, TriangleAlert, Volume2, VolumeX } from 'lucide-react'
import { chatDemoAnswers, chatSuggestions } from '../data/demo/demoData.js'
import { BackButton } from '../components/ui.jsx'
import { api, DATA_MODE } from '../api/client.js'

// Chatbot vocal (module chatbot du backend) :
// 1) la voix est reconnue dans le navigateur (Chrome/Edge), en derja (ar-TN) ou en français ;
// 2) sous-titres anglais pendant que l'agriculteur parle (/chatbot/captions) ;
// 3) la question est comprise puis traitée par le moteur : parcelle, rotation, impact (/chatbot/message) ;
// 4) la réponse peut être lue à voix haute (ElevenLabs, /chatbot/speak).
const WELCOME = { from: 'bot', text: 'Bonjour ! Je suis votre assistant AgriSense 🌱 Posez votre question à l\'écrit ou au micro, en derja ou en français. Choisissez une parcelle pour une réponse basée sur vos données.' }
const FALLBACK = "En mode démonstration, seules les questions suggérées ont une réponse d'exemple."
const SUGGESTIONS = ['شنوة نزرع العام هذا فول ولا قمح؟', 'Que planter cette année : fève ou blé ?', 'Est-ce que ma terre a besoin d\'eau ?']
const SR = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

export default function Chatbot() {
  const demo = DATA_MODE === 'demo'
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [feedback, setFeedback] = useState({})
  const [parcels, setParcels] = useState([])
  const [parcelId, setParcelId] = useState('')
  const [nRate, setNRate] = useState('')
  const [speechLang, setSpeechLang] = useState('ar-TN')
  const [replyLang, setReplyLang] = useState('fr')
  const [subtitles, setSubtitles] = useState(true)
  const [voice, setVoice] = useState(true)
  const [listening, setListening] = useState(false)
  const [live, setLive] = useState({ heard: '', en: '' })
  const [thinking, setThinking] = useState(false)
  const endRef = useRef(null)
  const recRef = useRef(null)
  const state = useRef({ running: false, paused: false, busy: false, timer: null, cache: {} })

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, live])
  useEffect(() => {
    if (demo) return
    api.listParcels().then((list) => { setParcels(list); if (list[0]) setParcelId(list[0].id) }).catch(() => {})
  }, [demo])
  useEffect(() => () => { state.current.running = false; recRef.current?.stop() }, [])

  const translate = async (text) => {
    if (!subtitles || demo) return ''
    const cache = state.current.cache
    if (cache[text] === undefined) cache[text] = (await api.chatbotCaptions(text)).en || ''
    return cache[text]
  }

  const pauseMic = () => { if (recRef.current && state.current.running) { state.current.paused = true; try { recRef.current.stop() } catch { /* déjà arrêté */ } } }
  const resumeMic = () => { if (recRef.current && state.current.running && state.current.paused) { state.current.paused = false; try { recRef.current.start() } catch { /* déjà démarré */ } } }

  const speak = async (text) => {
    try {
      const blob = await api.chatbotSpeak(text)
      pauseMic() // le micro ne doit pas entendre la réponse
      const audio = new Audio(URL.createObjectURL(blob))
      await new Promise((done) => { audio.onended = done; audio.onerror = done; audio.play().catch(done) })
    } catch (e) {
      setMessages((m) => [...m, { from: 'bot', text: `Voix indisponible : ${e.message}`, error: true }])
    }
  }

  const ask = async (raw, caption = '') => {
    const question = raw.trim()
    if (!question || state.current.busy) return
    setInput('')
    if (demo) {
      setMessages((m) => [...m, { from: 'user', text: question }, { from: 'bot', text: chatDemoAnswers[question] || FALLBACK, demo: true }])
      return
    }
    state.current.busy = true
    setMessages((m) => [...m, { from: 'user', text: question, caption }])
    setThinking(true)
    try {
      const r = await api.chatbotMessage({ text: question, parcelleId: parcelId, nRate, lang: replyLang })
      setMessages((m) => [...m, {
        from: 'bot', text: r.text, figures: r.figures || [], needs: r.needs_info || [],
        meta: [r.understood, r.mode === 'lite' ? 'sans parcelle (règles simplifiées)' : null].filter(Boolean).join(' · '), rated: true,
      }])
      if (voice && r.text) await speak(r.text)
    } catch (e) {
      setMessages((m) => [...m, { from: 'bot', text: e.message, error: true }])
    } finally {
      state.current.busy = false
      setThinking(false)
      resumeMic()
    }
  }

  // Micro continu : sous-titres pendant la phrase, question envoyée à la fin de la phrase.
  const toggleMic = () => {
    if (!SR) return
    if (state.current.running) {
      state.current.running = false
      recRef.current?.stop()
      setListening(false)
      setLive({ heard: '', en: '' })
      return
    }
    const rec = new SR()
    rec.lang = speechLang
    rec.continuous = true
    rec.interimResults = true
    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) {
          const text = res[0].transcript.trim()
          if (!text) continue
          setLive({ heard: text, en: '' })
          translate(text).then((en) => { setLive({ heard: '', en: '' }); ask(text, en) }).catch(() => { setLive({ heard: '', en: '' }); ask(text) })
        } else interim += res[0].transcript
      }
      if (interim.trim()) {
        const heard = interim.trim()
        setLive((l) => ({ ...l, heard }))
        clearTimeout(state.current.timer)
        state.current.timer = setTimeout(() => {
          if (heard.length >= 4) translate(heard).then((en) => setLive((l) => (l.heard === heard ? { ...l, en } : l))).catch(() => {})
        }, 500)
      }
    }
    rec.onerror = (e) => {
      if (e.error === 'not-allowed') setMessages((m) => [...m, { from: 'bot', text: 'Micro refusé : autorisez le micro dans le navigateur.', error: true }])
    }
    rec.onend = () => { if (state.current.running && !state.current.paused) { try { rec.start() } catch { /* relance */ } } }
    recRef.current = rec
    state.current.running = true
    state.current.paused = false
    setListening(true)
    rec.start()
  }

  return (
    <div className="chat-page">
      <BackButton />
      {!demo && (
        <div className="chat-options">
          <label>Parcelle
            <select value={parcelId} onChange={(e) => setParcelId(e.target.value)}>
              <option value="">Aucune (règles simplifiées)</option>
              {parcels.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>Azote réel (kg N/ha)
            <input type="number" min="0" value={nRate} onChange={(e) => setNRate(e.target.value)} placeholder="facultatif" />
          </label>
          <label>Langue parlée
            <select value={speechLang} onChange={(e) => setSpeechLang(e.target.value)} disabled={listening}>
              <option value="ar-TN">Derja (ar-TN)</option><option value="ar-SA">Arabe (ar-SA)</option><option value="fr-FR">Français</option>
            </select>
          </label>
          <label>Réponse
            <select value={replyLang} onChange={(e) => setReplyLang(e.target.value)}>
              <option value="fr">Français</option><option value="en">English</option>
            </select>
          </label>
          <label className="check"><input type="checkbox" checked={subtitles} onChange={(e) => setSubtitles(e.target.checked)} /> Sous-titres anglais</label>
          <button type="button" className={`icon-btn voice-toggle ${voice ? 'on' : ''}`} onClick={() => setVoice((v) => !v)} title="Réponse vocale (ElevenLabs)">
            {voice ? <Volume2 size={18} /> : <VolumeX size={18} />} Voix
          </button>
        </div>
      )}
      <div className="chat-layout">
        <aside className="chat-mascot">
          <div className="mascot"><Bot size={64} /></div>
          <div className="suggestions">
            {(demo ? chatSuggestions : SUGGESTIONS).map((s) => <button key={s} onClick={() => ask(s)} dir="auto">{s}</button>)}
          </div>
        </aside>
        <section className="chat-thread">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.from}`}>
              {m.from === 'bot' && <span className="bubble-avatar"><Bot size={18} /></span>}
              <div className={m.error ? 'bubble-error' : ''}>
                <p dir="auto">{m.text}</p>
                {m.caption && <p className="caption">🇬🇧 {m.caption}</p>}
                {m.figures?.length > 0 && <ul className="figures">{m.figures.map((f) => <li key={f}>{f}</li>)}</ul>}
                {m.needs?.length > 0 && <ul className="needs">{m.needs.map((n) => <li key={n}><TriangleAlert size={13} /> {n}</li>)}</ul>}
                {m.meta && <small className="muted">{m.meta}</small>}
                {(m.demo || m.rated) && (
                  <div className="bubble-foot">
                    {m.demo && <span className="badge badge-demo">Démo</span>}
                    <button className={`icon-btn ${feedback[i] === 'up' ? 'on' : ''}`} onClick={() => setFeedback((f) => ({ ...f, [i]: 'up' }))} aria-label="Utile"><ThumbsUp size={15} /></button>
                    <button className={`icon-btn ${feedback[i] === 'down' ? 'on' : ''}`} onClick={() => setFeedback((f) => ({ ...f, [i]: 'down' }))} aria-label="Pas utile"><ThumbsDown size={15} /></button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {(live.heard || live.en) && (
            <div className="live-caption">
              <p dir="rtl">{live.heard}</p>
              {live.en && <p className="caption">🇬🇧 {live.en}</p>}
            </div>
          )}
          {thinking && <div className="bubble bot"><span className="bubble-avatar"><Bot size={18} /></span><div><p className="muted">L'assistant réfléchit…</p></div></div>}
          <div ref={endRef} />
        </section>
      </div>
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} dir="auto"
          placeholder={listening ? 'Je vous écoute… (parlez, la question part à la fin de la phrase)' : 'Posez votre question…'} />
        <button type="button" className={`mic-btn ${listening ? 'on' : ''}`} onClick={toggleMic} disabled={!SR}
          aria-label="Parler" title={SR ? (listening ? 'Arrêter le micro' : 'Parler') : 'Dictée non disponible sur ce navigateur (essayez Chrome ou Edge)'}><Mic size={19} /></button>
        <button className="btn btn-primary round" aria-label="Envoyer"><Send size={18} /></button>
      </form>
    </div>
  )
}
