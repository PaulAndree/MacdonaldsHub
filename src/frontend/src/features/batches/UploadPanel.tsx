import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, NetworkError, StorageError, api } from "../../api/client";
import { putFile } from "../../api/upload";
import { es } from "../../i18n/es";
import { ErrorState } from "../../ui/StateViews";
import { batchKeys } from "./queries";
import type { BatchUpload } from "./types";

type Phase = "idle" | "preparing" | "uploading" | "finishing";

/**
 * Select a file, upload it straight to storage with the temporary permission, and ask for its
 * processing. If the upload does not complete the batch is discarded, so nothing is left blocking the
 * user (one unconfirmed batch per user).
 */
export default function UploadPanel({ disabled = false }: { disabled?: boolean }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [uploadFailed, setUploadFailed] = useState(false);

  async function start(file: File) {
    setError(null);
    setUploadFailed(false);
    setProgress(null);
    setPhase("preparing");
    let batchId: string | null = null;
    let reachedStorage = false;
    try {
      const created = await api.post<BatchUpload>("/api/batches", { fileName: file.name, sizeBytes: file.size });
      batchId = created.batch.id;
      setPhase("uploading");
      reachedStorage = true;
      await putFile(created.upload, file, (fraction) => setProgress(Math.round(fraction * 100)));
      setPhase("finishing");
      await api.post(`/api/batches/${batchId}/uploaded`);
      void queryClient.invalidateQueries({ queryKey: batchKeys.pending });
      navigate(`/lotes/${batchId}`);
    } catch (caught) {
      // A batch whose file did not reach storage would block the next upload: drop it.
      if (batchId) {
        await api.post(`/api/batches/${batchId}/discard`).catch(() => undefined);
        await queryClient.invalidateQueries({ queryKey: batchKeys.pending });
      }
      setPhase("idle");
      if (reachedStorage && (caught instanceof StorageError || caught instanceof NetworkError)) {
        setUploadFailed(true);
      } else if (caught instanceof ApiError && caught.code === "unconfirmed_batch_exists") {
        await queryClient.invalidateQueries({ queryKey: batchKeys.pending });
        setError(caught);
      } else {
        setError(caught);
      }
    } finally {
      if (input.current) input.current.value = "";
    }
  }

  const busy = phase !== "idle";
  return (
    <div className="card">
      <label htmlFor="xlsx-file">{es.import.fileLabel}</label>
      <p>
        <input
          id="xlsx-file"
          ref={input}
          type="file"
          accept=".xlsx"
          disabled={disabled || busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void start(file);
          }}
        />
      </p>
      {phase === "preparing" && <p role="status">{es.import.preparing}</p>}
      {phase === "uploading" && (
        <p role="status">
          <progress max={100} value={progress ?? undefined} aria-label={es.import.uploading(progress)} />{" "}
          {es.import.uploading(progress)}
        </p>
      )}
      {phase === "finishing" && <p role="status">{es.import.finishing}</p>}
      {uploadFailed && (
        <div className="notice notice--danger" role="alert">
          {es.import.uploadFailed}
        </div>
      )}
      {error != null && !uploadFailed && <ErrorState mutation error={error} />}
    </div>
  );
}

