import { createContext, useContext, useState, useEffect, useCallback } from "react";

const ThemeContext = createContext(null);
export const useTheme = () => useContext(ThemeContext);

const getInitial = () => {
  const saved = localStorage.getItem("theme");
  return saved === "light" || saved === "dark" ? saved : "dark"; // design default: dark
};

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(getInitial);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
