import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { assets, search } from '../lib/api'
import {
  Search,
  Type,
  Tag,
  Loader,
  Image,
  ArrowRight,
  ImageIcon,
  Settings2,
  ChevronDown,
} from 'lucide-react'

function SearchResult({ asset, rank }) {
  return (
    <Link
      to={`/assets/${asset.id}`}
      className="card image-grid-item group"
    >
      <div className="aspect-square bg-gray-100 relative overflow-hidden">
        <img
          src={assets.getFileUrl(asset.id)}
          alt={asset.original_filename}
          className="w-full h-full object-cover"
          loading="lazy"
        />

        {rank !== undefined && (
          <div className="absolute top-2 right-2">
            <span className="badge-info">
              #{rank}
            </span>
          </div>
        )}

        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white font-medium">View Details</span>
        </div>
      </div>

      <div className="p-3">
        <p className="font-medium text-sm truncate" title={asset.original_filename}>
          {asset.original_filename}
        </p>
        {asset.ml_labels && asset.ml_labels.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {asset.ml_labels.slice(0, 3).map((label) => (
              <span
                key={label}
                className="text-xs px-1.5 py-0.5 bg-gray-100 rounded text-gray-600"
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  )
}

function ImagePicker({ onSelect, selectedId }) {
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    assets.list(1, 50, 'completed')
      .then((data) => setImages(data.items))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="spinner" />
      </div>
    )
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Image className="w-12 h-12 mx-auto mb-2 text-gray-300" />
        <p>No images available. Upload some images first.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2 max-h-64 overflow-y-auto p-2 bg-gray-50 rounded-lg">
      {images.map((img) => (
        <button
          key={img.id}
          onClick={() => onSelect(img)}
          className={`aspect-square rounded-lg overflow-hidden border-2 transition-all ${
            selectedId === img.id
              ? 'border-primary-500 ring-2 ring-primary-200'
              : 'border-transparent hover:border-gray-300'
          }`}
        >
          <img
            src={assets.getFileUrl(img.id)}
            alt={img.original_filename}
            className="w-full h-full object-cover"
          />
        </button>
      ))}
    </div>
  )
}

function SearchOptions({ limit, setLimit, threshold, setThreshold, showThreshold = true }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="btn-secondary text-sm"
      >
        <Settings2 className="w-4 h-4" />
        Options
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 p-4 z-10">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Max Results: {limit}
              </label>
              <input
                type="range"
                min="5"
                max="100"
                step="5"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>5</span>
                <span>100</span>
              </div>
            </div>

            {showThreshold && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Similarity: {(threshold * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="0.9"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0%</span>
                  <span>90%</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function LabelDropdown({ value, onChange, labels, loading }) {
  return (
    <div className="relative">
      <Tag className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input pl-12 pr-4 py-4 text-lg appearance-none cursor-pointer"
        disabled={loading}
      >
        <option value="">Select a label...</option>
        {labels.map((label) => (
          <option key={label} value={label}>
            {label}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
    </div>
  )
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchType, setSearchType] = useState('text')
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [label, setLabel] = useState(searchParams.get('label') || '')
  const [availableLabels, setAvailableLabels] = useState([])
  const [labelsLoading, setLabelsLoading] = useState(false)
  const [selectedImage, setSelectedImage] = useState(null)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  // Search options
  const [limit, setLimit] = useState(20)
  const [threshold, setThreshold] = useState(0.1)

  // Load available labels when label search is selected
  useEffect(() => {
    if (searchType === 'label' && availableLabels.length === 0) {
      setLabelsLoading(true)
      search.getAvailableLabels()
        .then(setAvailableLabels)
        .catch(console.error)
        .finally(() => setLabelsLoading(false))
    }
  }, [searchType])

  // Handle label search from URL param
  useEffect(() => {
    const labelParam = searchParams.get('label')
    if (labelParam) {
      setSearchType('label')
      setLabel(labelParam)
      performLabelSearch(labelParam)
    }
  }, [])

  const performTextSearch = async (q) => {
    if (!q.trim()) return

    setLoading(true)
    setSearched(true)
    try {
      const data = await search.byText(q, limit, threshold)
      setResults(data.results)
    } catch (err) {
      console.error('Search failed:', err)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const performLabelSearch = async (l) => {
    if (!l.trim()) return

    setLoading(true)
    setSearched(true)
    try {
      const data = await search.byLabel(l, limit)
      // Label search returns assets directly, not results with similarity
      setResults(data.map((asset) => ({ asset })))
    } catch (err) {
      console.error('Search failed:', err)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const performSimilarSearch = async (imageId) => {
    if (!imageId) return

    setLoading(true)
    setSearched(true)
    try {
      const data = await search.similar(imageId, limit, threshold)
      setResults(data.results)
    } catch (err) {
      console.error('Search failed:', err)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (searchType === 'text') {
      setSearchParams({ q: query })
      performTextSearch(query)
    } else if (searchType === 'label') {
      setSearchParams({ label })
      performLabelSearch(label)
    } else if (searchType === 'similar' && selectedImage) {
      setSearchParams({ similar: selectedImage.id })
      performSimilarSearch(selectedImage.id)
    }
  }

  const suggestedQueries = [
    'a sunset over the ocean',
    'people at a restaurant',
    'a cat sleeping',
    'mountain landscape',
    'city at night',
    'food photography',
  ]

  return (
    <div className="p-8">
      <div className="max-w-3xl mx-auto mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Search Images</h1>
        <p className="text-gray-600 mb-6">
          Find images using natural language, labels, or visual similarity
        </p>

        {/* Search type tabs */}
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setSearchType('text')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              searchType === 'text'
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Type className="w-4 h-4" />
            Text Search
          </button>
          <button
            onClick={() => setSearchType('label')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              searchType === 'label'
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Tag className="w-4 h-4" />
            Label Search
          </button>
          <button
            onClick={() => setSearchType('similar')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              searchType === 'similar'
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            Similar Image
          </button>

          <div className="ml-auto">
            <SearchOptions
              limit={limit}
              setLimit={setLimit}
              threshold={threshold}
              setThreshold={setThreshold}
              showThreshold={searchType !== 'label'}
            />
          </div>
        </div>

        {/* Search form */}
        <form onSubmit={handleSubmit}>
          {searchType === 'text' && (
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Describe what you're looking for..."
                className="input pl-12 pr-24 py-4 text-lg"
              />
              <button
                type="submit"
                disabled={loading}
                className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary"
              >
                {loading ? <Loader className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                Search
              </button>
            </div>
          )}

          {searchType === 'label' && (
            <div className="space-y-3">
              <LabelDropdown
                value={label}
                onChange={setLabel}
                labels={availableLabels}
                loading={labelsLoading}
              />
              {labelsLoading && (
                <p className="text-sm text-gray-500 flex items-center gap-2">
                  <Loader className="w-4 h-4 animate-spin" />
                  Loading available labels...
                </p>
              )}
              {!labelsLoading && availableLabels.length === 0 && (
                <p className="text-sm text-gray-500">
                  No labels found. Upload and process some images first.
                </p>
              )}
              {label && (
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full py-3"
                >
                  {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  Search for "{label}"
                </button>
              )}
            </div>
          )}

          {searchType === 'similar' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">Select an image to find similar ones:</p>
              <ImagePicker
                onSelect={(img) => setSelectedImage(img)}
                selectedId={selectedImage?.id}
              />
              {selectedImage && (
                <div className="flex items-center gap-4 p-3 bg-primary-50 rounded-lg">
                  <img
                    src={assets.getFileUrl(selectedImage.id)}
                    alt={selectedImage.original_filename}
                    className="w-16 h-16 object-cover rounded"
                  />
                  <div className="flex-1">
                    <p className="font-medium text-sm">{selectedImage.original_filename}</p>
                    <p className="text-xs text-gray-500">Selected for similarity search</p>
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="btn-primary"
                  >
                    {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    Find Similar
                  </button>
                </div>
              )}
            </div>
          )}
        </form>

        {/* Suggested queries */}
        {searchType === 'text' && !searched && (
          <div className="mt-4">
            <p className="text-sm text-gray-500 mb-2">Try searching for:</p>
            <div className="flex flex-wrap gap-2">
              {suggestedQueries.map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setQuery(q)
                    performTextSearch(q)
                  }}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm text-gray-700 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-gray-500">Searching...</p>
          </div>
        </div>
      ) : searched && results.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-gray-500">
          <Image className="w-16 h-16 mb-4 text-gray-300" />
          <p className="text-lg font-medium">No results found</p>
          <p className="text-sm mt-1">Try a different search query or lower the similarity threshold</p>
        </div>
      ) : results.length > 0 ? (
        <div>
          <p className="text-sm text-gray-500 mb-4">
            Found {results.length} {results.length === 1 ? 'result' : 'results'}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {results.map(({ asset }, index) => (
              <SearchResult
                key={asset.id}
                asset={asset}
                rank={index + 1}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
