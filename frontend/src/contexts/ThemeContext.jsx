import { createContext, useContext, useState, useEffect } from 'react'

const themes = {
  modern: {
    name: 'Modern',
    description: 'Clean, minimal design',
    class: 'theme-modern',
  },
  retro: {
    name: 'Retro Pixel',
    description: '8-bit pixel art style',
    class: 'theme-retro',
  },
  dark: {
    name: 'Dark Mode',
    description: 'Easy on the eyes',
    class: 'theme-dark',
  },
  synthwave: {
    name: 'Synthwave',
    description: 'Neon 80s vibes',
    class: 'theme-synthwave',
  },
}

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('visualvault-theme')
    return saved && themes[saved] ? saved : 'modern'
  })

  useEffect(() => {
    // Remove all theme classes
    Object.values(themes).forEach((t) => {
      document.documentElement.classList.remove(t.class)
    })
    // Add current theme class
    document.documentElement.classList.add(themes[theme].class)
    localStorage.setItem('visualvault-theme', theme)
  }, [theme])

  const value = {
    theme,
    setTheme,
    themes,
    currentTheme: themes[theme],
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

export default ThemeContext
