import { Link } from "react-router-dom";
import { es } from "../i18n/es";

export default function NotFound() {
  return (
    <>
      <h1>{es.titles.notFound}</h1>
      <p>{es.notFound.text}</p>
      <p>
        <Link to="/">{es.notFound.back}</Link>
      </p>
    </>
  );
}
