import Link from "next/link";

const navigation = [
  { href: "/", label: "Overview" },
  { href: "/lab/", label: "Fingerprint Lab" },
  { href: "/science/", label: "Science" },
] as const;

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell site-header__inner">
        <Link className="wordmark" href="/" aria-label="ScoutLens home">
          <span className="wordmark__mark" aria-hidden="true">
            SL
          </span>
          <span>ScoutLens</span>
        </Link>
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
