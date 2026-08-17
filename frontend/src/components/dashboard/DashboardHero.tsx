/** Dashboard-only hero banner — an original, self-contained SVG illustration (pump jacks, a
 * derrick, a flare stack) silhouetted against a dusk-over-the-oilfield gradient. No external
 * image files and no network request, matching this app's "everything local" convention.
 * Deliberately NOT theme-reactive (always the dark dusk gradient with light text) — a hero
 * banner is allowed to be its own fixed moment rather than flipping with light/dark mode, and
 * it guarantees text contrast regardless of the viewer's OS theme. Used only here, not as a
 * shared PageHeader replacement — every other page keeps the plain PageHeader.
 */
export function DashboardHero({ title, description }: { title: string; description: string }) {
  return (
    <div className="relative h-44 overflow-hidden rounded-lg border border-zinc-800 sm:h-48">
      <svg
        viewBox="0 0 800 220"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-0 h-full w-full"
        role="img"
        aria-label="Illustration of pump jacks and a derrick against a dusk sky"
      >
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#09090b" />
            <stop offset="55%" stopColor="#27150a" />
            <stop offset="100%" stopColor="#92400e" />
          </linearGradient>
          <radialGradient id="glow" cx="50%" cy="100%" r="75%">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
          </radialGradient>

          <g id="pumpjack" fill="none" stroke="#09090b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M -22 70 L 0 18 L 22 70" />
            <rect x="-3" y="8" width="6" height="24" fill="#09090b" stroke="none" />
            <path d="M -38 6 L 26 13" />
            <path d="M -38 6 Q -47 -1 -41 -9" />
            <circle cx="22" cy="14" r="7" fill="#09090b" stroke="none" />
            <path d="M 22 20 L 22 70" />
            <rect x="-10" y="70" width="20" height="6" fill="#09090b" stroke="none" />
          </g>

          <g id="derrick" fill="none" stroke="#09090b" strokeWidth="2.5" strokeLinecap="round">
            <path d="M 0 100 L -17 0 L 17 0 Z" />
            <path d="M -12 75 L 12 75 M -8 50 L 8 50 M -4 25 L 4 25" />
          </g>
        </defs>

        <rect x="0" y="0" width="800" height="220" fill="url(#sky)" />
        <rect x="0" y="0" width="800" height="220" fill="url(#glow)" />

        {/* ground silhouette */}
        <path d="M 0 190 L 800 190 L 800 220 L 0 220 Z" fill="#09090b" />

        {/* derrick + flare */}
        <use href="#derrick" transform="translate(120 90) scale(0.9)" />
        <path d="M 120 -12 Q 114 -22 120 -30 Q 126 -22 120 -12 Z" fill="#fbbf24" />

        {/* pump jack skyline, varied scale for depth */}
        <use href="#pumpjack" transform="translate(300 120) scale(0.85)" />
        <use href="#pumpjack" transform="translate(460 108) scale(1.05)" />
        <use href="#pumpjack" transform="translate(640 122) scale(0.75)" />
      </svg>

      <div className="absolute inset-0 flex flex-col justify-center gap-1 bg-gradient-to-t from-black/40 via-transparent p-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-400">OG-PIOS</p>
        <h1 className="text-2xl font-semibold text-white">{title}</h1>
        <p className="max-w-xl text-sm text-zinc-200">{description}</p>
      </div>
    </div>
  );
}
