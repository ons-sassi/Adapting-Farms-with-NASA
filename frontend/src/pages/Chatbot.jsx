import { useEffect, useRef, useState } from 'react'
import { Bot, Mic, Send, ThumbsDown, ThumbsUp } from 'lucide-react'
import { chatDemoAnswers, chatSuggestions } from '../data/demo/demoData.js'
import { BackButton } from '../components/ui.jsx'
import { api, DATA_MODE } from '../api/client.js'

const WELCOME = { from: 'bot', text: 'Bonjour ! Je suis votre assistant AgriSense 🌱 Posez-moi vos questions sur votre terrain, vos cultures ou vos recommandations.' }
const FALLBACK = "L'assistant n'est pas encore connecté : en mode démonstration, seules les questions suggérées ont une réponse d'exemple."

const SR = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

export default function Chatbot() {
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [feedback, setFeedback] = useState({})
  const [listening, setListening] = useState(false)
  const endRef = useRef(null)
  const recRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const [thinking, setThinking] = useState(false)

  const ask = async (text) => {
    const question = text.trim()
    if (!question || thinking) return
    setInput('')
    if (DATA_MODE === 'demo') {
      setMessages((m) => [...m, { from: 'user', text: question }, { from: 'bot', text: chatDemoAnswers[question] || FALLBACK, demo: true }])
      return
    }
    // Historique envoyé au backend (sans le message d'accueil), 10 derniers échanges max.
    const history = messages.slice(1).slice(-10).map((m) => ({ role: m.from === 'user' ? 'user' : 'assistant', content: m.text }))
    setMessages((m) => [...m, { from: 'user', text: question }])
    setThinking(true)
    try {
      const { answer } = await api.chat(question, history)
      setMessages((m) => [...m, { from: 'bot', text: answer, rated: true }])
    } catch (e) {
      setMessages((m) => [...m, { from: 'bot', text: e.message, error: true }])
    } finally {
      setThinking(false)
    }
  }

  // Micro : dicte la question dans la langue du navigateur, puis l'envoie
  const listen = () => {
    if (!SR) return
    if (listening) { recRef.current?.stop(); return }
    const rec = new SR()
    rec.lang = navigator.language || 'fr-FR'
    rec.interimResults = false
    rec.onresult = (e) => ask(e.results[0][0].transcript)
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recRef.current = rec
    setListening(true)
    rec.start()
  }

  return (
    <div className="chat-page">
      <BackButton />
      <div className="chat-layout">
        <aside className="chat-mascot">
          <div className="mascot"><Bot size={64} /></div>
          <div className="suggestions">
            {chatSuggestions.map((s) => <button key={s} onClick={() => ask(s)}>{s}</button>)}
          </div>
        </aside>
        <section className="chat-thread">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.from}`}>
              {m.from === 'bot' && <span className="bubble-avatar"><Bot size={18} /></span>}
              <div>
                <p>{m.text}</p>
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
          {thinking && <div className="bubble bot"><span className="bubble-avatar"><Bot size={18} /></span><div><p className="muted">L'assistant réfléchit…</p></div></div>}
          <div ref={endRef} />
        </section>
      </div>
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={listening ? 'Je vous écoute…' : 'Posez votre question…'} />
        <button type="button" className={`mic-btn ${listening ? 'on' : ''}`} onClick={listen} disabled={!SR}
          aria-label="Parler" title={SR ? 'Parler' : 'Dictée non disponible sur ce navigateur (essayez Chrome)'}><Mic size={19} /></button>
        <button className="btn btn-primary round" aria-label="Envoyer"><Send size={18} /></button>
      </form>
    </div>
  )
}
