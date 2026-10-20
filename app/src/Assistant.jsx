import { useEffect, useRef, useState } from 'react'

// アシスタントの画面（コマ7。教員が用意したもの）
//   - 質問を API（/api/chat）に送り、応答を「少しずつ」受け取って表示する
//   - 会話の ID をブラウザに覚えておき、画面を開き直したら API から履歴を読み直す
//   - キーはここ（ブラウザ）には一切ない。ブラウザが知っているのは自分の API の URL だけ

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const STORAGE_KEY = 'cloud2-conversation-id'

// SSE（text/event-stream）の本文を読み、イベント（JSON）を1つずつ onEvent に渡す
async function readEvents(response, onEvent) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // イベントとイベントの間は空行（\n\n）で区切られている
    let index
    while ((index = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)))
      }
    }
  }
}

export default function Assistant() {
  const [conversationId, setConversationId] = useState(() => localStorage.getItem(STORAGE_KEY))
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [info, setInfo] = useState('')
  const [error, setError] = useState('')
  const startedAt = useRef(0)

  // 画面を開いたとき: 覚えている会話があれば、履歴を API から読み直す
  useEffect(() => {
    if (!conversationId) return
    fetch(`${API_BASE_URL}/api/conversations?id=${encodeURIComponent(conversationId)}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((items) => setMessages(items))
      .catch(() => setError('会話の履歴を読めませんでした'))
  }, [])

  function newConversation() {
    localStorage.removeItem(STORAGE_KEY)
    setConversationId(null)
    setMessages([])
    setInfo('')
    setError('')
  }

  // 最後のメッセージ（応答中のアシスタントの吹き出し）に文字を足す
  function appendToLast(text) {
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      return [...prev.slice(0, -1), { ...last, content: last.content + text }]
    })
  }

  async function send(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || busy) return
    setBusy(true)
    setError('')
    setInfo('')
    setInput('')
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '' },
    ])
    startedAt.current = performance.now()
    let firstAt = 0

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversationId, message: question }),
      })
      await readEvents(res, (event) => {
        if (event.type === 'start') {
          localStorage.setItem(STORAGE_KEY, event.conversationId)
          setConversationId(event.conversationId)
          setInfo(`モデルに送ったメッセージ: ${event.sentMessages} 件`)
        } else if (event.type === 'delta') {
          if (!firstAt) firstAt = performance.now()
          appendToLast(event.text)
        } else if (event.type === 'error') {
          setError(event.message)
        } else if (event.type === 'end') {
          const first = ((firstAt - startedAt.current) / 1000).toFixed(1)
          const total = ((performance.now() - startedAt.current) / 1000).toFixed(1)
          setInfo((prev) => `${prev} ／ 最初の文字まで ${first} 秒・全体 ${total} 秒`)
        }
      })
    } catch (err) {
      setError(`応答を受け取れませんでした（${err.message}）`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="assistant">
      <div className="assistant-head">
        <h2>アシスタント</h2>
        <button type="button" className="secondary" onClick={newConversation} disabled={busy}>
          新しい会話
        </button>
      </div>

      <div className="chat-log">
        {messages.length === 0 && <p className="hint">社内の手続きなどについて質問できます（架空の会社の設定です）。</p>}
        {messages.map((m, i) => (
          // React は文字列を自動でエスケープして表示する。LLM の出力も「信頼できない入力」として扱う
          <div key={i} className={`bubble ${m.role}`}>
            {m.content || (busy && i === messages.length - 1 ? '…' : '')}
          </div>
        ))}
      </div>

      {info && <p className="info">{info}</p>}
      {error && <p className="message">{error}</p>}

      <form className="chat-form" onSubmit={send}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={1000}
          placeholder="質問を入力（架空の内容だけ）"
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          {busy ? '応答中…' : '送信'}
        </button>
      </form>
    </section>
  )
}
