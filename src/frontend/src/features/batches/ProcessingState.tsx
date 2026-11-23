import { es } from "../../i18n/es";

/** The file is stored and being read. Nothing definitive exists yet. */
export default function ProcessingState() {
  return (
    <div className="card" role="status">
      <h2>{es.import.processingTitle}</h2>
      <p>{es.import.processingText}</p>
      <progress aria-label={es.import.processingTitle} />
    </div>
  );
}
