import { useEffect, useState } from 'react'
import Assistant from './Assistant.jsx'

// API の URL は、ビルドのときに azd が設定ファイル（.env.production.local）に書き込む
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export default function App() {
  const [items, setItems] = useState([])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [message, setMessage] = useState('')

  async function load() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/inquiries`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setItems(await res.json())
    } catch (e) {
      setMessage(`一覧を取得できませんでした（${e.message}）`)
    }
  }

  async function submit(e) {
    e.preventDefault()
    setMessage('')
    const res = await fetch(`${API_BASE_URL}/api/inquiries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, body }),
    })
    const data = await res.json()
    if (!res.ok) {
      setMessage(data.error ?? `登録できませんでした（HTTP ${res.status}）`)
      return
    }
    setTitle('')
    setBody('')
    await load()
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <main>
      <h1>問い合わせ管理</h1>

      <Assistant />

      <h2>問い合わせの登録</h2>

      <form onSubmit={submit}>
        <label>
          件名
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} />
        </label>
        <label>
          本文
          <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={2000} rows={4} />
        </label>
        <button type="submit">登録する</button>
      </form>

      {message && <p className="message">{message}</p>}

      <h2>一覧</h2>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <div className="meta">
              <span className="status">{item.status}</span>
              <span>{new Date(item.createdAt).toLocaleString('ja-JP')}</span>
            </div>
            {/* React は文字列を自動でエスケープして表示する（XSS 対策。2年次に学んだ内容） */}
            <strong>{item.title}</strong>
            <p>{item.body}</p>
          </li>
        ))}
      </ul>
    </main>
  )
}
