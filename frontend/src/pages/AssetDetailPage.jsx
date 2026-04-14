import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { assets, search } from '../lib/api'
import {
  ArrowLeft,
  Download,
  Trash2,
  Tag,
  Palette,
  Grid3X3,
  Search,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader,
  ExternalLink,
  RefreshCw,
} from 'lucide-react'

const statusConfig = {
  pending: { icon: Clock, class: 'badge-warning', label: 'Pending' },
  processing: { icon: Loader, class: 'badge-info', label: 'Processing' },
  completed: { icon: CheckCircle, class: 'badge-success', label: 'Completed' },
  failed: { icon: AlertCircle, class: 'badge-error', label: 'Failed' },
}

function ColorSwatch({ color }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
      <div
        className="w-10 h-10 rounded-lg shadow-inner border border-gray-200"
        style={{ backgroundColor: color.hex }}
      />
      <div className="flex-1">
        <p className="font-mono text-sm font-medium">{color.hex}</p>
        <p className="text-xs text-gray-500">
          RGB({color.rgb.join(', ')}) · {color.percentage}%
        </p>
      </div>
    </div>
  )
}

function SimilarAssets({ assetId }) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    search.similar(assetId, 6, 0.3)
      .then((data) => setResults(data.results))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [assetId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="spinner" />
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <p className="text-gray-500 text-sm text-center py-8">
        No similar images found
      </p>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-2">
      {results.map(({ asset, similarity }) => (
        <Link
          key={asset.id}
          to={`/assets/${asset.id}`}
          className="aspect-square bg-gray-100 rounded-lg overflow-hidden relative group"
        >
          <img
            src={`/api/v1/assets/${asset.id}/file`}
            alt={asset.original_filename}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <span className="text-white text-xs font-medium">
              {(similarity * 100).toFixed(0)}% match
            </span>
          </div>
        </Link>
      ))}
    </div>
  )
}

function SegmentationPanel({ assetId }) {
  const [numClusters, setNumClusters] = useState(5)
  const [segmentedUrl, setSegmentedUrl] = useState(null)
  const [clusterInfo, setClusterInfo] = useState(null)
  const [loading, setLoading] = useState(false)

  const generateSegmentation = async () => {
    setLoading(true)
    try {
      const info = await assets.getSegmentInfo(assetId, numClusters)
      setClusterInfo(info.clusters)
      setSegmentedUrl(`/api/v1/assets/${assetId}/segment?num_clusters=${numClusters}&t=${Date.now()}`)
    } catch (err) {
      console.error('Segmentation failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-700">Colors:</label>
        <input
          type="range"
          min="2"
          max="12"
          value={numClusters}
          onChange={(e) => setNumClusters(parseInt(e.target.value))}
          className="flex-1"
        />
        <span className="text-sm font-mono w-8">{numClusters}</span>
        <button
          onClick={generateSegmentation}
          disabled={loading}
          className="btn-primary text-sm py-1.5"
        >
          {loading ? <div className="spinner w-4 h-4" /> : <Grid3X3 className="w-4 h-4" />}
          Generate
        </button>
      </div>

      {segmentedUrl && (
        <div className="space-y-4">
          <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
            <img
              src={segmentedUrl}
              alt="Segmented"
              className="w-full h-full object-contain"
            />
          </div>

          {clusterInfo && (
            <div className="grid grid-cols-2 gap-2">
              {clusterInfo.map((color, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 p-2 bg-gray-50 rounded"
                >
                  <div
                    className="w-6 h-6 rounded border border-gray-200"
                    style={{ backgroundColor: color.hex }}
                  />
                  <span className="text-xs font-mono">{color.hex}</span>
                  <span className="text-xs text-gray-500 ml-auto">
                    {color.percentage}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AssetDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [asset, setAsset] = useState(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [activeTab, setActiveTab] = useState('info')

  const loadAsset = async () => {
    try {
      const data = await assets.get(id)
      setAsset(data)
    } catch (err) {
      console.error('Failed to load asset:', err)
      if (err.response?.status === 404) {
        navigate('/')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAsset()
  }, [id])

  // Auto-refresh for processing assets
  useEffect(() => {
    if (asset && (asset.status === 'pending' || asset.status === 'processing')) {
      const interval = setInterval(loadAsset, 3000)
      return () => clearInterval(interval)
    }
  }, [asset?.status])

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this image?')) return

    setDeleting(true)
    try {
      await assets.delete(id)
      navigate('/')
    } catch (err) {
      console.error('Failed to delete:', err)
      alert('Failed to delete image')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="spinner" />
      </div>
    )
  }

  if (!asset) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Asset not found</p>
      </div>
    )
  }

  const status = statusConfig[asset.status] || statusConfig.pending

  const tabs = [
    { id: 'info', label: 'Info', icon: Tag },
    { id: 'colors', label: 'Colors', icon: Palette },
    { id: 'segment', label: 'Segment', icon: Grid3X3 },
    { id: 'similar', label: 'Similar', icon: Search },
  ]

  return (
    <div className="h-full flex flex-col lg:flex-row">
      {/* Image section */}
      <div className="lg:flex-1 bg-gray-900 flex items-center justify-center p-4 min-h-[300px] lg:min-h-0">
        <div className="relative max-w-full max-h-full">
          {asset.status === 'completed' ? (
            <img
              src={`/api/v1/assets/${asset.id}/file`}
              alt={asset.original_filename}
              className="max-w-full max-h-[70vh] object-contain rounded-lg"
            />
          ) : (
            <div className="w-64 h-64 bg-gray-800 rounded-lg flex flex-col items-center justify-center">
              <status.icon className={`w-16 h-16 text-gray-600 ${asset.status === 'processing' ? 'animate-spin' : ''}`} />
              <p className="text-gray-400 mt-4">{status.label}</p>
              {asset.error_message && (
                <p className="text-red-400 text-sm mt-2 max-w-xs text-center">
                  {asset.error_message}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Details panel */}
      <div className="lg:w-96 bg-white border-l border-gray-200 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="font-semibold truncate" title={asset.original_filename}>
                {asset.original_filename}
              </h1>
              <span className={status.class}>
                <status.icon className={`w-3 h-3 mr-1 ${asset.status === 'processing' ? 'animate-spin' : ''}`} />
                {status.label}
              </span>
            </div>
          </div>

          <div className="flex gap-2">
            {asset.status === 'completed' && (
              <a
                href={`/api/v1/assets/${asset.id}/file`}
                download={asset.original_filename}
                className="btn-secondary flex-1 text-sm"
              >
                <Download className="w-4 h-4" />
                Download
              </a>
            )}
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="btn-danger flex-1 text-sm"
            >
              {deleting ? <div className="spinner w-4 h-4" /> : <Trash2 className="w-4 h-4" />}
              Delete
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-primary-600 border-b-2 border-primary-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="w-4 h-4 mx-auto mb-1" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === 'info' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  File Info
                </h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Dimensions</dt>
                    <dd className="font-medium">
                      {asset.width && asset.height
                        ? `${asset.width} × ${asset.height}`
                        : '—'}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Size</dt>
                    <dd className="font-medium">
                      {(asset.file_size / 1024 / 1024).toFixed(2)} MB
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Type</dt>
                    <dd className="font-medium">{asset.content_type}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Uploaded</dt>
                    <dd className="font-medium">
                      {new Date(asset.created_at).toLocaleString()}
                    </dd>
                  </div>
                  {asset.processed_at && (
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Processed</dt>
                      <dd className="font-medium">
                        {new Date(asset.processed_at).toLocaleString()}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>

              {asset.ml_labels && asset.ml_labels.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                    ML Labels
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {asset.ml_labels.map((label) => (
                      <Link
                        key={label}
                        to={`/search?label=${encodeURIComponent(label)}`}
                        className="px-3 py-1.5 bg-primary-50 text-primary-700 rounded-full text-sm font-medium hover:bg-primary-100 transition-colors"
                      >
                        {label}
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {asset.ml_text && (
                <div>
                  <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                    Extracted Text
                  </h3>
                  <p className="text-sm bg-gray-50 p-3 rounded-lg">
                    {asset.ml_text}
                  </p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'colors' && (
            <div>
              {asset.ml_colors && asset.ml_colors.length > 0 ? (
                <div className="space-y-2">
                  {asset.ml_colors.map((color, i) => (
                    <ColorSwatch key={i} color={color} />
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm text-center py-8">
                  {asset.status === 'completed'
                    ? 'No colors extracted'
                    : 'Processing...'}
                </p>
              )}
            </div>
          )}

          {activeTab === 'segment' && (
            <SegmentationPanel assetId={asset.id} />
          )}

          {activeTab === 'similar' && (
            <SimilarAssets assetId={asset.id} />
          )}
        </div>
      </div>
    </div>
  )
}
