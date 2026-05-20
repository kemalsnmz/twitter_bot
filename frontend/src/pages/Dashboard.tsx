import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'

function StatCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl p-6`}>
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const qc = useQueryClient()
  const { data: stats, isLoading } = useQuery({ queryKey: ['stats'], queryFn: api.stats, refetchInterval: 30000 })
  const { data: recent } = useQuery({ queryKey: ['recent'], queryFn: api.recent, refetchInterval: 30000 })

  const pipeline = useMutation({
    mutationFn: api.runPipeline,
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries(), 5000)
    },
  })

  if (isLoading) return <p className="text-gray-400">Yükleniyor...</p>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <button
          onClick={() => pipeline.mutate()}
          disabled={pipeline.isPending}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {pipeline.isPending ? 'Çalışıyor...' : 'Pipeline Çalıştır'}
        </button>
      </div>

      {pipeline.isSuccess && (
        <div className="bg-green-900/40 border border-green-700 rounded-lg px-4 py-3 text-green-400 text-sm">
          Pipeline başlatıldı. İçerik toplanıyor...
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Toplam İçerik" value={stats?.total_content ?? 0} color="text-white" />
        <StatCard label="Onay Bekleyen" value={stats?.pending_tweets ?? 0} color="text-yellow-400" />
        <StatCard label="Yayınlanan Tweet" value={stats?.published_total ?? 0} color="text-green-400" />
      </div>

      {stats?.last_run && (
        <p className="text-gray-500 text-sm">Son çalışma: {new Date(stats.last_run).toLocaleString('tr-TR')}</p>
      )}

      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Son Yayınlananlar</h2>
        {!recent?.length ? (
          <p className="text-gray-500">Henüz yayınlanan tweet yok.</p>
        ) : (
          <div className="space-y-3">
            {recent.map((t: any) => (
              <div key={t.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <p className="text-gray-100 text-sm mb-2">{t.tweet_text}</p>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>{new Date(t.published_at).toLocaleString('tr-TR')}</span>
                  {t.tweet_id && (
                    <a
                      href={`https://twitter.com/i/web/status/${t.tweet_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-400 hover:underline"
                    >
                      Twitter'da gör
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
