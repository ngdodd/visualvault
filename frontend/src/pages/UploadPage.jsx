import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { assets } from '../lib/api'
import {
  Upload,
  Image,
  X,
  CheckCircle,
  AlertCircle,
  FileImage,
} from 'lucide-react'

function UploadItem({ file, progress, status, error, onRemove }) {
  return (
    <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
      <div className="w-12 h-12 bg-gray-200 rounded-lg flex items-center justify-center flex-shrink-0">
        <FileImage className="w-6 h-6 text-gray-500" />
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{file.name}</p>
        <p className="text-xs text-gray-500">
          {(file.size / 1024 / 1024).toFixed(2)} MB
        </p>

        {status === 'uploading' && (
          <div className="mt-2">
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {status === 'error' && (
          <p className="text-xs text-red-600 mt-1">{error}</p>
        )}
      </div>

      <div className="flex-shrink-0">
        {status === 'pending' && (
          <button
            onClick={onRemove}
            className="p-1 text-gray-400 hover:text-gray-600"
          >
            <X className="w-5 h-5" />
          </button>
        )}
        {status === 'uploading' && (
          <div className="spinner" />
        )}
        {status === 'success' && (
          <CheckCircle className="w-5 h-5 text-green-600" />
        )}
        {status === 'error' && (
          <AlertCircle className="w-5 h-5 text-red-600" />
        )}
      </div>
    </div>
  )
}

export default function UploadPage() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const navigate = useNavigate()

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith('image/')
    )
    addFiles(droppedFiles)
  }, [])

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files)
    addFiles(selectedFiles)
    e.target.value = '' // Reset input
  }

  const addFiles = (newFiles) => {
    const fileItems = newFiles.map((file) => ({
      id: Math.random().toString(36).substr(2, 9),
      file,
      progress: 0,
      status: 'pending',
      error: null,
    }))
    setFiles((prev) => [...prev, ...fileItems])
  }

  const removeFile = (id) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const uploadAll = async () => {
    const pendingFiles = files.filter((f) => f.status === 'pending')
    if (pendingFiles.length === 0) return

    setUploading(true)

    for (const fileItem of pendingFiles) {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileItem.id ? { ...f, status: 'uploading' } : f
        )
      )

      try {
        await assets.upload(fileItem.file, (progress) => {
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileItem.id ? { ...f, progress } : f
            )
          )
        })

        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileItem.id ? { ...f, status: 'success', progress: 100 } : f
          )
        )
      } catch (err) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileItem.id
              ? {
                  ...f,
                  status: 'error',
                  error: err.response?.data?.detail || 'Upload failed',
                }
              : f
          )
        )
      }
    }

    setUploading(false)
  }

  const successCount = files.filter((f) => f.status === 'success').length
  const pendingCount = files.filter((f) => f.status === 'pending').length

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Upload Images</h1>
        <p className="text-gray-600 mt-1">
          Drag and drop or select images to upload
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={`dropzone ${dragActive ? 'active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="fileInput"
          multiple
          accept="image/*"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div className="flex flex-col items-center">
          <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-4">
            <Upload className="w-8 h-8 text-primary-600" />
          </div>
          <p className="text-lg font-medium text-gray-700">
            Drop images here, or{' '}
            <label
              htmlFor="fileInput"
              className="text-primary-600 hover:text-primary-700 cursor-pointer"
            >
              browse
            </label>
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Supports JPG, PNG, GIF, WebP (max 10MB each)
          </p>
        </div>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-900">
              {files.length} {files.length === 1 ? 'file' : 'files'} selected
            </h3>
            {pendingCount > 0 && (
              <button
                onClick={() => setFiles([])}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Clear all
              </button>
            )}
          </div>

          {files.map((fileItem) => (
            <UploadItem
              key={fileItem.id}
              file={fileItem.file}
              progress={fileItem.progress}
              status={fileItem.status}
              error={fileItem.error}
              onRemove={() => removeFile(fileItem.id)}
            />
          ))}

          <div className="flex items-center justify-between pt-4">
            {successCount > 0 && (
              <p className="text-sm text-green-600">
                {successCount} {successCount === 1 ? 'file' : 'files'} uploaded successfully
              </p>
            )}

            <div className="flex items-center gap-3 ml-auto">
              {successCount > 0 && (
                <button
                  onClick={() => navigate('/')}
                  className="btn-secondary"
                >
                  View Gallery
                </button>
              )}

              {pendingCount > 0 && (
                <button
                  onClick={uploadAll}
                  disabled={uploading}
                  className="btn-primary"
                >
                  {uploading ? (
                    <>
                      <div className="spinner" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      Upload {pendingCount} {pendingCount === 1 ? 'file' : 'files'}
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
