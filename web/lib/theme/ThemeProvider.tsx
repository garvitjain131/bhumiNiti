import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const THEME_KEY = "lpip.theme";

type ThemeContextValue = { theme: Theme; toggleTheme: () => void };
const ThemeContext = createContext<ThemeContextValue>({ theme: "light", toggleTheme: () => {} });

/**
 * Light / dark theme. The choice is stored in localStorage and applied as <html data-theme>; an inline script in
 * _document.tsx applies it before the first paint so the page never flashes the wrong theme.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* storage unavailable: the choice lasts for this page only */
      }
      return next;
    });
  }, []);

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
