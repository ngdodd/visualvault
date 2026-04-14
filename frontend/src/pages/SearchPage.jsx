import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { search } from '../lib/api'
import {
  Search,
  Type,
  Tag,
  Loader,
  Image,
  ArrowRight,
} from 'lucide-react'

function SearchResult({ asset, similarity }) {
  return (
    <Link
      to={`/assets/${asset.id}`}
      className="card image-grid-item group"
    >
      <div className="aspect-square bg-gray-100 relative overflow-hidden">
        <img
          src={`/api/v1/assets/${asset.id}/file`}
          alt={asset.original_filename}
          className="w-full h-full object-cover"
          loading="lazy"
        />

        {similarity !== undefined && (
          <div className="absolute top-2 right-2">
            <span className="badge-info">
              {(similarity * 100).toFixed(0)}% match
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

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchType, setSearchType] = useState('text')
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [label, setLabel] = useState(searchParams.get('label') || '')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

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
      const data = await search.byText(q, 50, 0.1)
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
      const data = await search.byLabel(l, 50)
      // Label search returns assets directly, not results with similarity
      setResults(data.map((asset) => ({ asset })))
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
    } else {
      setSearchParams({ label })
      performLabelSearch(label)
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
          Find images using natural language or labels
        </p>

        {/* Search type tabs */}
        <div className="flex gap-2 mb-4">
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
        </div>

        {/* Search form */}
        <form onSubmit={handleSubmit} className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          {searchType === 'text' ? (
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Describe what you're looking for..."
              className="input pl-12 pr-24 py-4 text-lg"
            />
          ) : (
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Enter a label (e.g., dog, landscape, food)"
              className="input pl-12 pr-24 py-4 text-lg"
            />
          )}
          <button
            type="submit"
            disabled={loading}
            className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary"
          >
            {loading ? (
              <Loader className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowRight className="w-4 h-4" />
            )}
            Search
          </button>
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
          <p className="text-sm mt-1">Try a different search query</p>
        </div>
      ) : results.length > 0 ? (
        <div>
          <p className="text-sm text-gray-500 mb-4">
            Found {results.length} {results.length === 1 ? 'result' : 'results'}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {results.map(({ asset, similarity }) => (
              <SearchResult
                key={asset.id}
                asset={asset}
                similarity={similarity}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
