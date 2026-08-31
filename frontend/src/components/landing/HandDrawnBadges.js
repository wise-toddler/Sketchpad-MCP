// Small hand-drawn SVG accents used across the landing page.

export function SketchUnderline({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 200 16"
      fill="none"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M3 10 C 40 4, 80 4, 120 8 C 150 11, 175 7, 197 6"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
        className="draw-stroke"
        style={{ ["--len"]: 220 }}
      />
    </svg>
  );
}

export function CurlyArrow({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 60 60" fill="none" aria-hidden="true">
      <path
        d="M8 6 C 30 8, 44 22, 40 46"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        className="draw-stroke"
        style={{ ["--len"]: 90 }}
      />
      <path d="M40 46 l -9 -6 M40 46 l 8 -8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
