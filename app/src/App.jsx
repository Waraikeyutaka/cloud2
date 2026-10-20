import { useEffect, useState } from 'react'
import Assistant from './Assistant.jsx'

// API の URL は、ビルドのときに azd が設定ファイル（.env.production.local）に書き込む
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export default function App() {
  const [items, setItems] = useState([])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [message, setMessage] = useState('')
  const [classifying, setClassifying] = useState(null) // 分類中の問い合わせの ID
  const [lastResult, setLastResult] = useState(null) // 直前の分類の結果（再試行の回数などを表示する）

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

  // AI で分類する（コマ8）。分類と振り分けはサーバー側で行い、画面は結果を表示するだけ
  async function classify(id) {
    setClassifying(id)
    setMessage('')
    try {
      const res = await fetch(`${API_BASE_URL}/api/inquiries/classify?id=${encodeURIComponent(id)}`, {
        method: 'POST',
      })
      const data = await res.json()
      if (!res.ok) {
        setMessage(data.error ?? `分類できませんでした（HTTP ${res.status}）`)
        return
      }
      setLastResult(data)
      await load()
    } catch (e) {
      setMessage(`分類できませんでした（${e.message}）`)
    } finally {
      setClassifying(null)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <main>
      <h1>問い合わせ管理</h1>

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

      {lastResult && (
        <p className="info">
          直前の分類: モデルを呼んだ回数 {lastResult.attempts} 回
          {lastResult.errors.length > 0 && `（検証に失敗した理由: ${lastResult.errors.join(' ／ ')}）`}
          {lastResult.fallback && ' → 上限まで失敗したので、人に回した'}
        </p>
      )}

      <h2>一覧</h2>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <div className="meta">
              <span className="status">{item.status}</span>
              <span>{new Date(item.createdAt).toLocaleString('ja-JP')}</span>
              {item.assignee && <span>担当: {item.assignee}</span>}
            </div>
            {/* React は文字列を自動でエスケープして表示する（XSS 対策。2年次に学んだ内容） */}
            <strong>{item.title}</strong>
            <p>{item.body}</p>
            {item.classification && (
              <div className="classification">
                <span className="tag">{item.classification.category}</span>
                <span className={`tag priority-${item.classification.priority}`}>
                  優先度 {item.classification.priority}
                </span>
                {item.classification.needs_human && <span className="tag">人が確認</span>}
                <span className="summary">要約: {item.classification.summary}</span>
              </div>
            )}
            <button
              type="button"
              className="secondary small"
              onClick={() => classify(item.id)}
              disabled={classifying !== null}
            >
              {classifying === item.id ? '分類中…' : item.classification ? 'AI で分類し直す' : 'AI で分類する'}
            </button>
          </li>
        ))}
      </ul>

      <Assistant />
    </main>
  )
}
