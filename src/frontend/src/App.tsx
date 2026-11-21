import { useEffect, useState } from "react";
import { ApiError, StorageError, getMe, runCheck, uploadTechnicalFile } from "./api";
import type { CheckResult, Me, UploadInfo } from "./api";

function describe(error: unknown): string {
  if (error instanceof StorageError) {
    return "El almacenamiento rechazó el archivo. Inténtelo de nuevo.";
  }
  if (error instanceof ApiError && error.status === 401) {
    return "Sesión no válida. Recargue la página para iniciar sesión.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "Acceso denegado: su usuario no tiene permiso para esta operación.";
  }
  return "No se pudo completar la operación.";
}

/** Platform verification screen only: identity, database round trip and a technical upload. */
export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState<string | null>(null);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [upload, setUpload] = useState<UploadInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch((e: unknown) => setMeError(describe(e)));
  }, []);

  async function onCheck() {
    setError(null);
    try {
      setCheck(await runCheck());
    } catch (e) {
      setError(describe(e));
    }
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setUpload(null);
    try {
      setUpload(await uploadTechnicalFile(file));
    } catch (e) {
      setError(describe(e));
    }
  }

  return (
    <main>
      <h1>Verificación técnica</h1>
      <p>Pantalla mínima de la plataforma base. No contiene funcionalidad de negocio.</p>

      <section aria-labelledby="identity">
        <h2 id="identity">Identidad</h2>
        {me && (
          <p>
            Usuario: <strong>{me.email ?? me.identifier}</strong> · Rol: <strong>{me.role}</strong>
          </p>
        )}
        {meError && <p role="alert">{meError}</p>}
        {!me && !meError && <p>Cargando…</p>}
      </section>

      <section aria-labelledby="db">
        <h2 id="db">Base de datos</h2>
        <button type="button" onClick={onCheck}>
          Comprobar base de datos
        </button>
        {check && (
          <p>
            Base de datos: <strong>{check.database}</strong> · Comprobaciones: {check.checks_total} ·
            Registrada: {check.recorded_at}
          </p>
        )}
      </section>

      <section aria-labelledby="storage">
        <h2 id="storage">Almacenamiento</h2>
        <label>
          Archivo técnico
          <input type="file" onChange={(e) => void onFile(e.target.files?.[0])} />
        </label>
        {upload && (
          <p>
            Archivo almacenado en <strong>{upload.container}</strong> ({upload.size} bytes)
          </p>
        )}
      </section>

      {error && <p role="alert">{error}</p>}
    </main>
  );
}
