import { useState, useEffect } from 'react'
import { assets } from '../lib/api'
import {
  Image,
  Grid3X3,
  Palette,
  Sparkles,
  ChevronRight,
  Download,
  RefreshCw,
} from 'lucide-react'

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

  const runSegmentation = async () => {
    if (!image) return

    setLoading(true)
    try {
      const info = await assets.getSegmentInfo(image.id, numClusters)
      setClusterInfo(info.clusters)
      setSegmentedUrl(`${assets.getSegmentUrl(image.id, numClusters)}&t=${Date.now()}`)
    } catch (err) {
      console.error('Segmentation failed:', err)
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
    <div className="space-y-6">
      {/* Controls */}
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
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          Run K-Means Segmentation
        </button>
      </div>

      {/* Results */}
      {segmentedUrl && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Original vs Segmented */}
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

      {/* Color Palette */}
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
  const [activeTool, setActiveTool] = useState('segmentation')

  const tools = [
    {
      id: 'segmentation',
      label: 'Color Segmentation',
      icon: Grid3X3,
      description: 'K-means clustering for color analysis',
    },
    // Future tools can be added here
  ]

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Image Analysis</h1>
        <p className="text-gray-600 mt-1">
          Select an image and run computer vision analysis tools
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
        {activeTool === 'segmentation' && (
          <ColorSegmentation image={selectedImage} />
        )}

        {/* Future Tools Preview */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">
            More Tools Coming Soon
          </h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <ComingSoonTool
              title="Edge Detection"
              description="Canny, Sobel, and other edge detectors"
              icon={Grid3X3}
            />
            <ComingSoonTool
              title="Object Detection"
              description="YOLO-based object detection"
              icon={Image}
            />
            <ComingSoonTool
              title="Style Transfer"
              description="Neural style transfer effects"
              icon={Palette}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
