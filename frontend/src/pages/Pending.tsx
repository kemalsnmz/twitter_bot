import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

interface PendingItem {
  id: number
  topic_label: string
  tweet_text: string
  source_name: string
  source_url: string
  title: string
  content_id: number
  created_at: string
}

function TweetCard({ item }: { item: PendingItem }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(item.tweet_text)
  const [done, setDone] = useState(false)

  const invalidate = () => { setDone(true); qc.invalidateQueries({ queryKey: ['pending'] }) }

  const approve = useMutation({ mutationFn: () => api.approve(item.id), onSuccess: invalidate })
  const reject = useMutation({ mutationFn: () => api.reject(item.id), onSuccess: invalidate })
  const edit = useMutation({ mutationFn: () => api.edit(item.id, editText), onSuccess: invalidate })

  if (done) return null

  const busy = approve.isPending || reject.isPending || edit.isPending

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Görsel */}
      <img
        src={`${api.imageUrl(item.content_id)}`}
        alt={item.title}
        className="w-full h-48 object-cover bg-gray-800"
        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
      />

      <div className="p-5 space-y-4">
        {/* Meta */}
        <div className="flex items-center justify-between">
          <span className="text-xs bg-blue-900/50 text-blue-300 border border-blue-700 rounded-full px-3 py-1">
            {item.topic_label}
          </span>
          <span className="text-xs text-gray-500">{new Date(item.created_at).toLocaleString('tr-TR')}</span>
        </div>

        {/* Kaynak */}
        <div>
          <p className="text-xs text-gray-500 mb-1">{item.source_name}</p>
          <a href={item.source_url} target="_blank" rel="noreferrer"
            className="text-xs text-gray-400 hover:text-blue-400 line-clamp-2 block">
            {item.title}
          </a>
        </div>

        {/* Tweet metni veya edit alanı */}
        {editing ? (
          <div className="space-y-2">
            <textarea
              value={editText}
              onChange={e => setEditText(e.target.value)}
              maxLength={257}
              rows={4}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 resize-none focus:outline-none focus:border-blue-500"
            />
            <p className={`text-xs text-right ${editText.length > 240 ? 'text-yellow-400' : 'text-gray-500'}`}>
              {editText.length}/257
            </p>
          </div>
        ) : (
          <p className="text-sm text-gray-100 bg-gray-800 rounded-lg p-3 leading-relaxed">
            {item.tweet_text}
          </p>
        )}

        {/* Hata mesajı */}
        {(approve.isError || reject.isError || edit.isError) && (
          <p className="text-red-400 text-xs">Hata oluştu. Tekrar dene.</p>
        )}

        {/* Butonlar */}
        <div className="flex gap-2">
          {editing ? (
            <>
              <button onClick={() => edit.mutate()} disabled={busy}
                className="flex-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                Kaydet & Yayınla
              </button>
              <button onClick={() => { setEditing(false); setEditText(item.tweet_text) }} disabled={busy}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-300 rounded-lg text-sm transition-colors">
                İptal
              </button>
            </>
          ) : (
            <>
              <button onClick={() => approve.mutate()} disabled={busy}
                className="flex-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                {approve.isPending ? '...' : 'Yayınla'}
              </button>
              <button onClick={() => setEditing(true)} disabled={busy}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-300 rounded-lg text-sm transition-colors">
                Düzenle
              </button>
              <button onClick={() => reject.mutate()} disabled={busy}
                className="px-4 py-2 bg-red-900/60 hover:bg-red-800 disabled:opacity-50 text-red-300 rounded-lg text-sm transition-colors">
                {reject.isPending ? '...' : 'Reddet'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Pending() {
  const { data: items, isLoading, refetch } = useQuery({
    queryKey: ['pending'],
    queryFn: api.pending,
    refetchInterval: 60000,
  })

  if (isLoading) return <p className="text-gray-400">Yükleniyor...</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Onay Kuyruğu</h1>
        <button onClick={() => refetch()}
          className="text-sm text-gray-400 hover:text-white transition-colors">
          Yenile
        </button>
      </div>

      {!items?.length ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg mb-2">Bekleyen tweet yok.</p>
          <p className="text-sm">Dashboard'dan pipeline'ı çalıştır.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {items.map((item: PendingItem) => (
            <TweetCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
