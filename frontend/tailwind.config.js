/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semantic enterprise theme tokens
        canvas: {
          light: "#E9ECE8",
          dark: "#171C19",
          DEFAULT: "var(--color-canvas)",
        },
        surface: {
          light: "#F4F5F2",
          dark: "#202622",
          DEFAULT: "var(--color-surface)",
        },
        panel: {
          light: "#DCE3DC",
          dark: "#2C352F",
          DEFAULT: "var(--color-panel)",
        },
        border: {
          light: "#CCD5CC",
          dark: "#39433C",
          DEFAULT: "var(--color-border)",
        },
        nav: {
          light: "#252B27",
          dark: "#121614",
          DEFAULT: "var(--color-nav-bg)",
        },
        accent: {
          light: "#267653",
          dark: "#42B883",
          DEFAULT: "var(--color-accent)",
          hover: "var(--color-accent-hover)",
          subtle: "var(--color-accent-subtle)",
        },
        primary: {
          light: "#1A201C",
          dark: "#F4F5F2",
          DEFAULT: "var(--color-text-primary)",
        },
        secondary: {
          light: "#4D5850",
          dark: "#C0C8C1",
          DEFAULT: "var(--color-text-secondary)",
        },
      },
    },
  },
  plugins: [],
};
