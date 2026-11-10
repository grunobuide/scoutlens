import Link from "next/link";

/**
 * Narrative §6.1's three frozen labels. D075 adds "Case study" as a fourth
 * item; `scoutlens-rdz.13` adds it here in the pull request that creates
 * `/case-study/`, so the link and its route land together (owner decision,
 * 2026-11-09, `scoutlens-rdz.7`). `public-identity.spec.ts` requires every
 * §6.1 item whose route the export has.
 */
const navigation = [
  { href: "/", label: "Overview" },
  { href: "/lab/", label: "Fingerprint Lab" },
  { href: "/science/", label: "How it works" },
] as const;

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell site-header__inner">
        {/* D075: the product descriptor sits under the wordmark, outside the
            home link, so the link's name stays the brand alone and the
            wordmark itself is unchanged. */}
        <div className="site-brand">
          <Link className="wordmark" href="/" aria-label="Yumusarái Labs home">
            <span className="wordmark__mark" aria-hidden="true">
              YL
            </span>
            <span>Yumusarái Labs</span>
          </Link>
          <p className="site-brand__descriptor">Player Fingerprint Lab</p>
        </div>
        <nav aria-label="Primary navigation">
          <ul className="site-nav">
            {navigation.map((item) => (
              <li key={item.href}>
                <Link href={item.href}>{item.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
