import { es } from "../i18n/es";

/** Identifies the test environment on every screen. Its recipients and metrics are not production activity. */
export default function EnvironmentBanner() {
  return (
    <div className="banner banner--test" role="note">
      {es.banners.test}
    </div>
  );
}
