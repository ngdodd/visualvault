import { useState, useEffect } from 'react'
import { assets, analysis } from '../lib/api'
import {
  Image,
  Grid3X3,
  Palette,
  Sparkles,
  ChevronRight,
  Box,
  Zap,
  BarChart3,
  RefreshCw,
  Eye,
  Layers,
  Paintbrush,
  Upload,
  Download,
} from 'lucide-react'

function LoadingOverlay({ message, subMessage }) {
  return (
    <div className="absolute inset-0 bg-white/90 flex flex-col items-center justify-center z-10 rounded-lg">
      <div className="relative">
        <div className="w-16 h-16 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
        <Sparkles className="w-6 h-6 text-primary-600 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
      </div>
      <p className="mt-4 font-medium text-gray-800">{message}</p>
      {subMessage && (
        <p className="mt-1 text-sm text-gray-500">{subMessage}</p>
      )}
    </div>
  )
}

function ImageSelector({ onSelect, selectedId }) {
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    assets.list(1, 100, 'completed')
      .then((data) => setImages(data.items))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="spinner" />
      </div>
    )
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Image className="w-16 h-16 mx-auto mb-3 text-gray-300" />
        <p className="font-medium">No images available</p>
        <p className="text-sm mt-1">Upload some images first to analyze them</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
      {images.map((img) => (
        <button
          key={img.id}
          onClick={() => onSelect(img)}
          className={`aspect-square rounded-lg overflow-hidden border-2 transition-all ${
            selectedId === img.id
              ? 'border-primary-500 ring-2 ring-primary-200 scale-105'
              : 'border-transparent hover:border-gray-300 hover:scale-102'
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

function ColorSegmentation({ image }) {
  const [numClusters, setNumClusters] = useState(5)
  const [segmentedUrl, setSegmentedUrl] = useState(null)
  const [clusterInfo, setClusterInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runSegmentation = async () => {
    if (!image) return

    setLoading(true)
    setError(null)
    try {
      const info = await assets.getSegmentInfo(image.id, numClusters)
      setClusterInfo(info.clusters)
      setSegmentedUrl(`${assets.getSegmentUrl(image.id, numClusters)}&t=${Date.now()}`)
    } catch (err) {
      console.error('Segmentation failed:', err)
      setError(err.response?.data?.detail || 'Segmentation failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (!image) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Grid3X3 className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>Select an image above to run color segmentation</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 relative">
      {/* Loading Overlay */}
      {loading && (
        <LoadingOverlay
          message="Running K-Means clustering..."
          subMessage={`Extracting ${numClusters} dominant colors`}
        />
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <p className="font-medium">Error</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4 p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center gap-3 flex-1 min-w-[200px]">
          <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
            Number of Colors:
          </label>
          <input
            type="range"
            min="2"
            max="16"
            value={numClusters}
            onChange={(e) => setNumClusters(parseInt(e.target.value))}
            className="flex-1"
          />
          <span className="text-lg font-mono font-bold text-primary-600 w-8">
            {numClusters}
          </span>
        </div>
        <button
          onClick={runSegmentation}
          disabled={loading}
          className="btn-primary"
        >
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Run K-Means
        </button>
      </div>

      {segmentedUrl && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <h4 className="font-medium text-gray-700 flex items-center gap-2">
              <ChevronRight className="w-4 h-4" />
              Original Image
            </h4>
            <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={assets.getFileUrl(image.id)}
                alt="Original"
                className="w-full h-full object-contain"
              />
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-medium text-gray-700 flex items-center gap-2">
              <ChevronRight className="w-4 h-4" />
              Segmented ({numClusters} colors)
            </h4>
            <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={segmentedUrl}
                alt="Segmented"
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}

      {clusterInfo && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-700 flex items-center gap-2">
            <Palette className="w-4 h-4" />
            Extracted Color Palette
          </h4>
          <div className="flex flex-wrap gap-3">
            {clusterInfo.map((color, i) => (
              <div
                key={i}
                className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 shadow-sm"
              >
                <div
                  className="w-12 h-12 rounded-lg shadow-inner border border-gray-200"
                  style={{ backgroundColor: color.hex }}
                />
                <div>
                  <p className="font-mono text-sm font-medium">{color.hex}</p>
                  <p className="text-xs text-gray-500">
                    RGB({color.rgb.join(', ')})
                  </p>
                  <p className="text-xs font-medium text-primary-600">
                    {color.percentage}% of image
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ObjectDetection({ image }) {
  const [models, setModels] = useState({})
  const [selectedModel, setSelectedModel] = useState('yolov8n')
  const [confidence, setConfidence] = useState(0.25)
  const [result, setResult] = useState(null)
  const [visualizeUrl, setVisualizeUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('')
  const [loadingSubMessage, setLoadingSubMessage] = useState('')
  const [error, setError] = useState(null)
  const [showComparison, setShowComparison] = useState(false)
  const [comparisonResult, setComparisonResult] = useState(null)
  const [metrics, setMetrics] = useState(null)

  // Load available models on mount
  useEffect(() => {
    analysis.getModels()
      .then((data) => setModels(data.models || {}))
      .catch(console.error)
  }, [])

  const runDetection = async () => {
    if (!image) return

    setLoading(true)
    setError(null)
    setResult(null)
    setVisualizeUrl(null)

    const modelInfo = models[selectedModel]
    const isLoaded = modelInfo?.loaded

    if (!isLoaded) {
      setLoadingMessage(`Loading ${modelInfo?.name || selectedModel}...`)
      setLoadingSubMessage('First run downloads the model (~' + (modelInfo?.size_mb || '?') + 'MB). This only happens once.')
    } else {
      setLoadingMessage('Running object detection...')
      setLoadingSubMessage('Analyzing image with ' + (modelInfo?.name || selectedModel))
    }

    try {
      const data = await analysis.detect(image.id, {
        model: selectedModel,
        confidence,
      })
      setResult(data)

      setLoadingMessage('Generating visualization...')
      setLoadingSubMessage('Drawing bounding boxes')

      setVisualizeUrl(
        `${analysis.getVisualizeUrl(image.id, { model: selectedModel, confidence })}&t=${Date.now()}`
      )

      // Refresh metrics and models (to update loaded state)
      const [metricsData, modelsData] = await Promise.all([
        analysis.getMetrics(),
        analysis.getModels(),
      ])
      setMetrics(metricsData.metrics)
      setModels(modelsData.models || {})
    } catch (err) {
      console.error('Detection failed:', err)
      setError(err.response?.data?.detail || 'Detection failed. Please try again.')
    } finally {
      setLoading(false)
      setLoadingMessage('')
      setLoadingSubMessage('')
    }
  }

  const runComparison = async () => {
    if (!image) return

    setLoading(true)
    setError(null)
    setShowComparison(true)
    setComparisonResult(null)

    setLoadingMessage('Comparing models...')
    setLoadingSubMessage('Running detection with YOLOv8 Nano, Small, and Medium')

    try {
      const data = await analysis.compare(image.id, ['yolov8n', 'yolov8s', 'yolov8m'], confidence)
      setComparisonResult(data)

      // Refresh models to update loaded state
      const modelsData = await analysis.getModels()
      setModels(modelsData.models || {})
    } catch (err) {
      console.error('Comparison failed:', err)
      setError(err.response?.data?.detail || 'Comparison failed. Please try again.')
    } finally {
      setLoading(false)
      setLoadingMessage('')
      setLoadingSubMessage('')
    }
  }

  if (!image) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Box className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>Select an image above to run object detection</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 relative">
      {/* Loading Overlay */}
      {loading && (
        <LoadingOverlay message={loadingMessage} subMessage={loadingSubMessage} />
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <p className="font-medium">Error</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

      {/* Controls */}
      <div className="p-4 bg-gray-50 rounded-lg space-y-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Model Selection */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Model:</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="input py-2 pr-8"
            >
              {Object.entries(models).map(([key, info]) => (
                <option key={key} value={key}>
                  {info.name} ({info.size_mb}MB)
                </option>
              ))}
            </select>
          </div>

          {/* Confidence Threshold */}
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <label className="text-sm font-medium text-gray-700">Confidence:</label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={confidence}
              onChange={(e) => setConfidence(parseFloat(e.target.value))}
              className="flex-1"
            />
            <span className="text-sm font-mono w-12">{(confidence * 100).toFixed(0)}%</span>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={runDetection}
            disabled={loading}
            className="btn-primary"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
            Detect Objects
          </button>
          <button
            onClick={runComparison}
            disabled={loading}
            className="btn-secondary"
          >
            <Layers className="w-4 h-4" />
            Compare Models
          </button>
        </div>
      </div>

      {/* Model Info */}
      {selectedModel && models[selectedModel] && (
        <div className={`p-3 rounded-lg text-sm ${models[selectedModel].loaded ? 'bg-green-50' : 'bg-blue-50'}`}>
          <div className="flex items-center gap-2">
            {models[selectedModel].loaded ? (
              <span className="flex items-center gap-1 text-green-700">
                <span className="w-2 h-2 bg-green-500 rounded-full" />
                <span className="font-medium">Model loaded</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-blue-700">
                <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                <span className="font-medium">Model not loaded yet</span>
              </span>
            )}
            <span className="text-gray-400">•</span>
            <span className={models[selectedModel].loaded ? 'text-green-600' : 'text-blue-600'}>
              {models[selectedModel].name}: {models[selectedModel].description}
            </span>
            <span className="text-gray-400">•</span>
            <span className={models[selectedModel].loaded ? 'text-green-500' : 'text-blue-500'}>
              {models[selectedModel].speed} inference
            </span>
          </div>
          {!models[selectedModel].loaded && (
            <p className="text-xs text-blue-500 mt-1">
              First detection will download the model (~{models[selectedModel].size_mb}MB)
            </p>
          )}
        </div>
      )}

      {/* Detection Results */}
      {visualizeUrl && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <h4 className="font-medium text-gray-700 flex items-center gap-2">
              <ChevronRight className="w-4 h-4" />
              Original Image
            </h4>
            <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={assets.getFileUrl(image.id)}
                alt="Original"
                className="w-full h-full object-contain"
              />
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-medium text-gray-700 flex items-center gap-2">
              <ChevronRight className="w-4 h-4" />
              Detected Objects ({result?.detections?.length || 0})
            </h4>
            <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={visualizeUrl}
                alt="Detection Result"
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}

      {/* Detections List */}
      {result && result.detections && result.detections.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-700 flex items-center gap-2">
            <Box className="w-4 h-4" />
            Detected Objects
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {result.detections.map((det, i) => (
              <div
                key={i}
                className="p-3 bg-white rounded-lg border border-gray-200 shadow-sm"
              >
                <p className="font-medium text-gray-800">{det.label}</p>
                <p className="text-sm text-gray-500">
                  Confidence: {(det.confidence * 100).toFixed(1)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inference Metrics */}
      {result && (
        <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg">
          <h4 className="font-medium text-gray-700 flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4" />
            Inference Metrics (MLOps)
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase">Model</p>
              <p className="font-mono font-medium">{result.model?.version}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Inference Time</p>
              <p className="font-mono font-medium">{result.metrics?.inference_time_ms}ms</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Detections</p>
              <p className="font-mono font-medium">{result.metrics?.num_detections}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Image Size</p>
              <p className="font-mono font-medium">{result.image?.width}×{result.image?.height}</p>
            </div>
          </div>
        </div>
      )}

      {/* Model Comparison */}
      {showComparison && comparisonResult && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-700 flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Model Comparison (A/B Testing)
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3">Model</th>
                  <th className="text-right py-2 px-3">Detections</th>
                  <th className="text-right py-2 px-3">Inference Time</th>
                  <th className="text-right py-2 px-3">Speed vs Nano</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comparisonResult.summary).map(([model, stats]) => (
                  <tr key={model} className="border-b border-gray-100">
                    <td className="py-2 px-3 font-medium">{model}</td>
                    <td className="text-right py-2 px-3">{stats.detections}</td>
                    <td className="text-right py-2 px-3">{stats.inference_time_ms.toFixed(1)}ms</td>
                    <td className="text-right py-2 px-3">
                      {model === 'yolov8n' ? '1.0x' :
                        `${(stats.inference_time_ms / comparisonResult.summary.yolov8n.inference_time_ms).toFixed(1)}x`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Aggregated Metrics */}
      {metrics && Object.keys(metrics).length > 0 && (
        <div className="p-4 bg-gray-50 rounded-lg">
          <h4 className="font-medium text-gray-700 flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4" />
            Session Metrics
          </h4>
          <div className="grid gap-4">
            {Object.entries(metrics).map(([model, stats]) => (
              <div key={model} className="flex items-center gap-4">
                <span className="font-mono text-sm w-24">{model}</span>
                <div className="flex-1 grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500">Inferences:</span>{' '}
                    <span className="font-medium">{stats.total_inferences}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Avg Time:</span>{' '}
                    <span className="font-medium">{stats.avg_inference_time_ms}ms</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Avg Detections:</span>{' '}
                    <span className="font-medium">{stats.avg_detections_per_image}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StyleTransfer({ image }) {
  const [styles, setStyles] = useState({})
  const [selectedStyle, setSelectedStyle] = useState('')
  const [strength, setStrength] = useState(1.0)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('')
  const [loadingSubMessage, setLoadingSubMessage] = useState('')
  const [error, setError] = useState(null)
  const [useCustomStyle, setUseCustomStyle] = useState(false)
  const [customStyleFile, setCustomStyleFile] = useState(null)
  const [customStylePreview, setCustomStylePreview] = useState(null)

  // Load available styles on mount
  useEffect(() => {
    analysis.getStyles()
      .then((data) => {
        setStyles(data.presets || {})
        const styleKeys = Object.keys(data.presets || {})
        if (styleKeys.length > 0) {
          setSelectedStyle(styleKeys[0])
        }
      })
      .catch(console.error)
  }, [])

  const handleCustomFileChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setCustomStyleFile(file)
      const reader = new FileReader()
      reader.onloadend = () => {
        setCustomStylePreview(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  const runStyleTransfer = async () => {
    if (!image) return

    setLoading(true)
    setError(null)
    setResult(null)

    if (useCustomStyle && customStyleFile) {
      setLoadingMessage('Applying custom style transfer...')
      setLoadingSubMessage('Loading VGG encoder and running optimization. This may take a moment.')
    } else {
      const styleInfo = styles[selectedStyle]
      setLoadingMessage(`Applying "${styleInfo?.name || selectedStyle}" style...`)
      setLoadingSubMessage('Running neural style transfer (this may take 10-20 seconds)')
    }

    try {
      if (useCustomStyle && customStyleFile) {
        const data = await analysis.customStyleTransfer(image.id, customStyleFile, strength)
        setResult({
          styled_image_url: `data:image/png;base64,${data.styled_image_base64}`,
          style: { name: 'Custom' },
        })
      } else {
        // For presets, fetch the image as blob and wait for it to complete
        const url = `${analysis.getStyledImageUrl(image.id, selectedStyle, strength)}&t=${Date.now()}`
        const response = await fetch(url)
        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(errorText || `Style transfer failed with status ${response.status}`)
        }
        const blob = await response.blob()
        const imageUrl = URL.createObjectURL(blob)
        setResult({
          styled_image_url: imageUrl,
          style: styles[selectedStyle],
        })
      }
    } catch (err) {
      console.error('Style transfer failed:', err)
      setError(err.message || err.response?.data?.detail || 'Style transfer failed. Please try again.')
    } finally {
      setLoading(false)
      setLoadingMessage('')
      setLoadingSubMessage('')
    }
  }

  const downloadStyledImage = () => {
    if (!result?.styled_image_url) return
    const link = document.createElement('a')
    link.href = result.styled_image_url
    link.download = `styled_${image.original_filename}`
    link.click()
  }

  if (!image) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Paintbrush className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>Select an image above to apply style transfer</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 relative">
      {/* Loading Overlay */}
      {loading && (
        <LoadingOverlay message={loadingMessage} subMessage={loadingSubMessage} />
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <p className="font-medium">Error</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

      {/* Style Selection */}
      <div className="p-4 bg-gray-50 rounded-lg space-y-4">
        {/* Toggle between preset and custom */}
        <div className="flex gap-2">
          <button
            onClick={() => setUseCustomStyle(false)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              !useCustomStyle
                ? 'bg-primary-100 text-primary-700'
                : 'bg-white text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Palette className="w-4 h-4 inline mr-2" />
            Preset Styles
          </button>
          <button
            onClick={() => setUseCustomStyle(true)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              useCustomStyle
                ? 'bg-primary-100 text-primary-700'
                : 'bg-white text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Upload className="w-4 h-4 inline mr-2" />
            Custom Style
          </button>
        </div>

        {!useCustomStyle ? (
          /* Preset Style Selection */
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {Object.entries(styles).map(([key, style]) => (
              <button
                key={key}
                onClick={() => setSelectedStyle(key)}
                className={`p-3 rounded-lg border-2 transition-all text-left ${
                  selectedStyle === key
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <p className="font-medium text-gray-800">{style.name}</p>
                <p className="text-xs text-gray-500 mt-1">{style.artist}</p>
              </button>
            ))}
          </div>
        ) : (
          /* Custom Style Upload */
          <div className="space-y-3">
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Upload a style image:</span>
              <input
                type="file"
                accept="image/*"
                onChange={handleCustomFileChange}
                className="mt-1 block w-full text-sm text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-lg file:border-0
                  file:text-sm file:font-medium
                  file:bg-primary-50 file:text-primary-700
                  hover:file:bg-primary-100"
              />
            </label>
            {customStylePreview && (
              <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
                <img
                  src={customStylePreview}
                  alt="Custom style"
                  className="w-20 h-20 object-cover rounded-lg"
                />
                <div>
                  <p className="font-medium text-gray-800">{customStyleFile?.name}</p>
                  <p className="text-xs text-gray-500">
                    Custom style image
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Strength Slider */}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
            Style Strength:
          </label>
          <input
            type="range"
            min="0.1"
            max="1.0"
            step="0.1"
            value={strength}
            onChange={(e) => setStrength(parseFloat(e.target.value))}
            className="flex-1"
          />
          <span className="text-sm font-mono w-12">{(strength * 100).toFixed(0)}%</span>
        </div>

        <button
          onClick={runStyleTransfer}
          disabled={loading || (useCustomStyle && !customStyleFile)}
          className="btn-primary"
        >
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Paintbrush className="w-4 h-4" />}
          Apply Style Transfer
        </button>
      </div>

      {/* Style Info */}
      {!useCustomStyle && selectedStyle && styles[selectedStyle] && (
        <div className="p-3 bg-purple-50 rounded-lg">
          <div className="flex items-center gap-2 text-purple-700">
            <Palette className="w-4 h-4" />
            <span className="font-medium">{styles[selectedStyle].name}</span>
            <span className="text-purple-400">•</span>
            <span>{styles[selectedStyle].artist}</span>
          </div>
          <p className="text-sm text-purple-600 mt-1">
            {styles[selectedStyle].description}
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                <ChevronRight className="w-4 h-4" />
                Original Image
              </h4>
              <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
                <img
                  src={assets.getFileUrl(image.id)}
                  alt="Original"
                  className="w-full h-full object-contain"
                />
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                <ChevronRight className="w-4 h-4" />
                Stylized Result
                <button
                  onClick={downloadStyledImage}
                  className="ml-auto text-primary-600 hover:text-primary-700"
                  title="Download styled image"
                >
                  <Download className="w-4 h-4" />
                </button>
              </h4>
              <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
                <img
                  src={result.styled_image_url}
                  alt="Stylized"
                  className="w-full h-full object-contain"
                />
              </div>
            </div>
          </div>

          {/* Info about the technique */}
          <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg">
            <h4 className="font-medium text-gray-700 flex items-center gap-2 mb-2">
              <Zap className="w-4 h-4" />
              About Neural Style Transfer
            </h4>
            <p className="text-sm text-gray-600">
              This uses the <strong>Gatys et al. optimization approach</strong> - a neural style transfer
              technique that iteratively optimizes the output image to match both the content of your image
              and the style patterns. It uses VGG-19 features and Gram matrices to capture artistic style.
            </p>
          </div>
        </>
      )}
    </div>
  )
}

function ComingSoonTool({ title, description, icon: Icon }) {
  return (
    <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg text-center">
      <Icon className="w-10 h-10 mx-auto mb-3 text-gray-300" />
      <h4 className="font-medium text-gray-600">{title}</h4>
      <p className="text-sm text-gray-400 mt-1">{description}</p>
      <span className="inline-block mt-3 px-3 py-1 bg-gray-100 rounded-full text-xs text-gray-500">
        Coming Soon
      </span>
    </div>
  )
}

export default function AnalyzePage() {
  const [selectedImage, setSelectedImage] = useState(null)
  const [activeTool, setActiveTool] = useState('detection')

  const tools = [
    {
      id: 'detection',
      label: 'Object Detection',
      icon: Box,
      description: 'YOLO-based object detection',
    },
    {
      id: 'segmentation',
      label: 'Color Segmentation',
      icon: Grid3X3,
      description: 'K-means clustering',
    },
    {
      id: 'style',
      label: 'Style Transfer',
      icon: Paintbrush,
      description: 'Neural style transfer with VGG-19',
    },
  ]

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Image Analysis</h1>
        <p className="text-gray-600 mt-1">
          Run computer vision models and explore MLOps concepts
        </p>
      </div>

      {/* Image Selection */}
      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Image className="w-5 h-5" />
          Select an Image
        </h2>
        <ImageSelector
          onSelect={setSelectedImage}
          selectedId={selectedImage?.id}
        />
        {selectedImage && (
          <div className="mt-4 p-3 bg-primary-50 rounded-lg flex items-center gap-4">
            <img
              src={assets.getFileUrl(selectedImage.id)}
              alt={selectedImage.original_filename}
              className="w-20 h-20 object-cover rounded-lg"
            />
            <div>
              <p className="font-medium">{selectedImage.original_filename}</p>
              <p className="text-sm text-gray-600">
                {selectedImage.width} × {selectedImage.height} • {(selectedImage.file_size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Analysis Tools */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5" />
          Analysis Tools
        </h2>

        {/* Tool Tabs */}
        <div className="flex gap-2 mb-6 border-b border-gray-200 pb-4">
          {tools.map((tool) => (
            <button
              key={tool.id}
              onClick={() => setActiveTool(tool.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                activeTool === tool.id
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <tool.icon className="w-4 h-4" />
              {tool.label}
            </button>
          ))}
        </div>

        {/* Tool Content */}
        {activeTool === 'detection' && (
          <ObjectDetection image={selectedImage} />
        )}

        {activeTool === 'segmentation' && (
          <ColorSegmentation image={selectedImage} />
        )}

        {activeTool === 'style' && (
          <StyleTransfer image={selectedImage} />
        )}

        {/* Future Tools Preview */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">
            More Tools Coming Soon
          </h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <ComingSoonTool
              title="Image Segmentation (SAM)"
              description="Segment Anything Model for pixel-level masks"
              icon={Layers}
            />
            <ComingSoonTool
              title="OCR / Text Extraction"
              description="Extract text from images with EasyOCR"
              icon={Box}
            />
            <ComingSoonTool
              title="Face Detection"
              description="Detect and optionally blur faces"
              icon={Eye}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
