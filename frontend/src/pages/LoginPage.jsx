import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Layers, Mail, Lock, ArrowRight } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex" style={{ backgroundColor: 'var(--color-bg)' }}>
      {/* Left side - Branding */}
      <div
        className="hidden lg:flex lg:w-1/2 p-12 flex-col justify-between"
        style={{ backgroundColor: 'var(--color-bg-secondary)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-12 h-12 flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-hover))',
              borderRadius: 'var(--radius-lg)',
            }}
          >
            <Layers className="w-7 h-7 text-white" />
          </div>
          <span className="text-2xl font-bold" style={{ color: 'var(--color-text)' }}>VisualVault</span>
        </div>

        <div>
          <h1 className="text-4xl font-bold mb-4" style={{ color: 'var(--color-text)' }}>
            Smart Visual Asset Intelligence
          </h1>
          <p className="text-lg leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
            Upload, analyze, and search your images using cutting-edge ML technology.
            Automatic labeling, color extraction, and semantic search powered by CLIP.
          </p>
        </div>

        <div className="flex gap-8">
          <div>
            <div className="text-3xl font-bold" style={{ color: 'var(--color-primary)' }}>CLIP</div>
            <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Semantic Search</div>
          </div>
          <div>
            <div className="text-3xl font-bold" style={{ color: 'var(--color-primary)' }}>K-Means</div>
            <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Color Analysis</div>
          </div>
          <div>
            <div className="text-3xl font-bold" style={{ color: 'var(--color-primary)' }}>Zero-Shot</div>
            <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Auto Labels</div>
          </div>
        </div>
      </div>

      {/* Right side - Login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div
              className="w-10 h-10 flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-hover))',
                borderRadius: 'var(--radius-lg)',
              }}
            >
              <Layers className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold" style={{ color: 'var(--color-text)' }}>VisualVault</span>
          </div>

          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--color-text)' }}>Welcome back</h2>
          <p className="mb-8" style={{ color: 'var(--color-text-secondary)' }}>Sign in to your account to continue</p>

          {error && (
            <div
              className="mb-6 p-4 rounded-lg text-sm"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid var(--color-error)',
                color: 'var(--color-error)',
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium mb-2"
                style={{ color: 'var(--color-text)' }}
              >
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--color-text-muted)' }} />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input pl-10"
                  placeholder="you@example.com"
                  required
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium mb-2"
                style={{ color: 'var(--color-text)' }}
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--color-text-muted)' }} />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input pl-10"
                  placeholder="Enter your password"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3"
            >
              {loading ? (
                <div className="spinner" />
              ) : (
                <>
                  Sign in
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center" style={{ color: 'var(--color-text-secondary)' }}>
            Don't have an account?{' '}
            <Link to="/register" style={{ color: 'var(--color-primary)' }} className="font-medium hover:opacity-80">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
