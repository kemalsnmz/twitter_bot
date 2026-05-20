import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

export default function Archive() {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useQuery({
    queryKey: ['archive', page],
    queryFn: () => api.archive(page),
  })

  if (isLoading) return <p className="text-gray-400">Yükleniyor...</p>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Arşiv</h1>

      {!data?.items?.length ? (
        <p className="text-gray-500">Henüz yayınlanan tweet yok.</p>
      ) : (
        <>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                  <th className="text-left px-4 py-3">Tarih</th>
                  <th className="text-left px-4 py-3">Tweet</th>
                  <th className="text-left px-4 py-3 w-24">Link</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((t: any) => (
                  <tr key={t.id} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap text-xs">
                      {new Date(t.published_at).toLocaleDateString('tr-TR')}
                      <br />
                      <span className="text-gray-600">{new Date(t.published_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-100">
                      <p className="line-clamp-2">{t.tweet_text}</p>
                      {t.source_url && (
                        <a href={t.source_url} target="_blank" rel="noreferrer"
                          className="text-xs text-gray-500 hover:text-blue-400 truncate block mt-1">
                          {t.source_url}
                        </a>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {t.tweet_id && (
                        <a href={`https://twitter.com/i/web/status/${t.tweet_id}`}
                          target="_blank" rel="noreferrer"
                          className="text-blue-400 hover:underline text-xs">
                          Görüntüle
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Sayfalama */}
          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded text-sm transition-colors">
                ←
              </button>
              <span className="text-gray-400 text-sm">{page} / {data.pages}</span>
              <button onClick={() => setPage(p => Math.min(data.pages, p + 1))} disabled={page === data.pages}
                className="px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded text-sm transition-colors">
                →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
