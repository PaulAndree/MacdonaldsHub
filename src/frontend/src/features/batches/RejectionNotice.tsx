import { Link } from "react-router-dom";
import { es } from "../../i18n/es";
import type { Batch } from "./types";

type Rejection = NonNullable<Batch["rejection"]>;

function reasonText(rejection: Rejection): string {
  switch (rejection.reason) {
    case "missing_required_header":
      return es.rejection.missing_required_header(rejection.detail);
    case "multiple_worksheets":
      return es.rejection.multiple_worksheets;
    case "corrupt_or_protected_file":
      return es.rejection.corrupt_or_protected_file;
  }
}

/** The whole file was rejected for its structure. There is no preview to review. */
export default function RejectionNotice({ rejection }: { rejection: Rejection }) {
  return (
    <div className="notice notice--danger" role="alert">
      <h2 style={{ marginTop: 0 }}>{es.rejection.title}</h2>
      <p>{reasonText(rejection)}</p>
      <p>
        {es.rejection.nothing} {es.rejection.fix}
      </p>
      <Link to="/importar">{es.import.chooseAnother}</Link>
    </div>
  );
}
