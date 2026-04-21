import { useState } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import { Palette, Check, Monitor, Moon, Gamepad2, Sparkles } from 'lucide-react'

const themeIcons = {
  modern: Monitor,
  retro: Gamepad2,
  dark: Moon,
  synthwave: Sparkles,
}

const themeColors = {
  modern: 'bg-gradient-to-br from-indigo-500 to-purple-500',
  retro: 'bg-gradient-to-br from-cyan-400 to-green-400',
  dark: 'bg-gradient-to-br from-slate-700 to-slate-900',
  synthwave: 'bg-gradient-to-br from-pink-500 to-purple-600',
}

export default function ThemeSwitcher({ compact = false }) {
  const { theme, setTheme, themes } = useTheme()
  const [isOpen, setIsOpen] = useState(false)

  if (compact) {
    return (
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-2 rounded-lg hover:bg-[var(--color-bg-tertiary)] transition-colors"
          title="Change theme"
        >
          <Palette className="w-5 h-5" />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute right-0 mt-2 w-56 rounded-lg shadow-lg z-50 border overflow-hidden"
              style={{
                backgroundColor: 'var(--color-bg-secondary)',
                borderColor: 'var(--color-border)',
              }}
            >
              <div className="p-2">
                <p className="text-xs font-medium uppercase tracking-wider px-2 py-1 opacity-60">
                  Choose Theme
                </p>
                {Object.entries(themes).map(([key, t]) => {
                  const Icon = themeIcons[key]
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        setTheme(key)
                        setIsOpen(false)
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
                        theme === key
                          ? 'bg-[var(--color-primary-light)]'
                          : 'hover:bg-[var(--color-bg-tertiary)]'
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-md ${themeColors[key]} flex items-center justify-center`}>
                        <Icon className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1 text-left">
                        <p className="font-medium text-sm">{t.name}</p>
                        <p className="text-xs opacity-60">{t.description}</p>
                      </div>
                      {theme === key && (
                        <Check className="w-4 h-4 text-[var(--color-primary)]" />
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          </>
        )}
      </div>
    )
  }

  // Full theme selector (for settings page)
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <Palette className="w-5 h-5" />
        Theme
      </h3>
      <div className="grid grid-cols-2 gap-4">
        {Object.entries(themes).map(([key, t]) => {
          const Icon = themeIcons[key]
          return (
            <button
              key={key}
              onClick={() => setTheme(key)}
              className={`relative p-4 rounded-xl border-2 transition-all ${
                theme === key
                  ? 'border-[var(--color-primary)] bg-[var(--color-primary-light)]'
                  : 'border-[var(--color-border)] hover:border-[var(--color-border-hover)]'
              }`}
            >
              {theme === key && (
                <div className="absolute top-2 right-2">
                  <Check className="w-5 h-5 text-[var(--color-primary)]" />
                </div>
              )}
              <div className={`w-12 h-12 rounded-lg ${themeColors[key]} flex items-center justify-center mb-3 mx-auto`}>
                <Icon className="w-6 h-6 text-white" />
              </div>
              <p className="font-semibold">{t.name}</p>
              <p className="text-sm opacity-60 mt-1">{t.description}</p>
            </button>
          )
        })}
      </div>
    </div>
  )
}
