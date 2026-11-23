import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { es } from "../i18n/es";
import type { Area } from "./areas";

interface LayoutProps {
  /** Areas to offer in the navigation (already filtered by role). */
  areas: Area[];
  /** Banners shown above the header: example data, test environment. */
  banners?: ReactNode;
  /** Right side of the header: session information and Cerrar sesión. */
  session?: ReactNode;
  footer?: ReactNode;
  /** When set, shown instead of the routed screen (loading, no session, not authorized...). */
  gate?: ReactNode;
  /** A notice shown above the screen, for example a batch waiting for the user. */
  notice?: ReactNode;
}

export default function Layout({ areas, banners, session, footer, gate, notice }: LayoutProps) {
  return (
    <>
      <a className="skip-link" href="#contenido">
        {es.skipToContent}
      </a>
      {banners}
      <header className="app-header">
        <div className="app-header__bar">
          <div className="brand">
            <span className="brand__mark" aria-hidden="true">
              D
            </span>
            <p style={{ margin: 0 }}>
              <span className="brand__name">{es.appName}</span>
              <span className="brand__tagline">{es.tagline}</span>
            </p>
          </div>
          {session}
        </div>
      </header>
      {areas.length > 0 && (
        <nav className="app-nav" aria-label={es.nav.label}>
          <ul>
            {areas.map((area) => (
              <li key={area.id}>
                <NavLink to={area.path} end={area.path === "/incidencias"}>
                  {area.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      )}
      <main id="contenido" className="app-main" tabIndex={-1}>
        {notice}
        {gate ?? <Outlet />}
      </main>
      <footer className="app-footer">{footer}</footer>
    </>
  );
}
