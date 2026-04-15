import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { assets } from '../lib/api'
import {
  Image,
  Upload,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader,
} from 'lucide-react'

const statusConfig = {
  pending: { icon: Clock, class: 'badge-warning', label: 'Pending' },
  processing: { icon: Loader, class: 'badge-info', label: 'Processing' },
  completed: { icon: CheckCircle, class: 'badge-success', label: 'Completed' },
  failed: { icon: AlertCircle, class: 'badge-error', label: 'Failed' },
}

function AssetCard({ asset }) {
  const navigate = useNavigate()
  const status = statusConfig[asset.status] || statusConfig.pending

  return (
    <div
      onClick={() => navigate(`/assets/${asset.id}`)}
      className="card image-grid-item cursor-pointer group"
    >
      <div className="aspect-square bg-gray-100 relative overflow-hidden">
        {asset.status === 'completed' ? (
          <img
            src={assets.getFileUrl(asset.id)}
            alt={asset.original_filename}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <status.icon className={`w-12 h-12 text-gray-300 ${asset.status === 'processing' ? 'animate-spin' : ''}`} />
          </div>
        )}

        {/* Status badge */}
        <div className="absolute top-2 right-2">
          <span className={status.class}>
            <status.icon className={`w-3 h-3 mr-1 ${asset.status === 'processing' ? 'animate-spin' : ''}`} />
            {status.label}
          </span>
        </div>

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white font-medium">View Details</span>
        </div>
      </div>

      <div className="p-3">
        <p className="font-medium text-sm truncate" title={asset.original_filename}>
          {asset.original_filename}
        </p>
        <div className="flex items-center justify-between mt-1">
          <p className="text-xs text-gray-500">
            {asset.width && asset.height ? `${asset.width} × ${asset.height}` : 'Processing...'}
          </p>
          <p className="text-xs text-gray-500">
            {new Date(asset.created_at).toLocaleDateString()}
          </p>
        </div>

        {/* Labels preview */}
        {asset.ml_labels && asset.ml_labels.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {asset.ml_labels.slice(0, 3).map((label) => (
              <span key={label} className="text-xs px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">
                {label}
              </span>
            ))}
            {asset.ml_labels.length > 3 && (
              <span className="text-xs px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">
                +{asset.ml_labels.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function GalleryPage() {
  const [data, setData] = useState({ items: [], total: 0, pages: 1 })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState(null)

  const loadAssets = async () => {
    setLoading(true)
    try {
      const result = await assets.list(page, 20, statusFilter)
      setData(result)
    } catch (err) {
      console.error('Failed to load assets:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAssets()
  }, [page, statusFilter])

  // Auto-refresh for pending/processing assets
  useEffect(() => {
    const hasPending = data.items.some(
      (a) => a.status === 'pending' || a.status === 'processing'
    )
    if (hasPending) {
      const interval = setInterval(loadAssets, 5000)
      return () => clearInterval(interval)
    }
  }, [data.items])

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gallery</h1>
          <p className="text-gray-600 mt-1">
            {data.total} {data.total === 1 ? 'image' : 'images'} in your collection
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter || ''}
            onChange={(e) => {
              setStatusFilter(e.target.value || null)
              setPage(1)
            }}
            className="input w-40"
          >
            <option value="">All Status</option>
            <option value="completed">Completed</option>
            <option value="processing">Processing</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>

          <button
            onClick={loadAssets}
            className="btn-secondary"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <Link to="/upload" className="btn-primary">
            <Upload className="w-4 h-4" />
            Upload
          </Link>
        </div>
      </div>

      {/* Grid */}
      {loading && data.items.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <div className="spinner" />
        </div>
      ) : data.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-gray-500">
          <Image className="w-16 h-16 mb-4 text-gray-300" />
          <p className="text-lg font-medium">No images yet</p>
          <p className="text-sm mt-1">Upload your first image to get started</p>
          <Link to="/upload" className="btn-primary mt-4">
            <Upload className="w-4 h-4" />
            Upload Image
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {data.items.map((asset) => (
              <AssetCard key={asset.id} asset={asset} />
            ))}
          </div>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <span className="px-4 py-2 text-sm">
                Page {page} of {data.pages}
              </span>

              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
                className="btn-secondary"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
