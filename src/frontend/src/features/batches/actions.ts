import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useAction } from "../../ui/useAction";
import { batchKeys } from "./queries";
import type { Batch } from "./types";

/** Cancel an unconfirmed batch: the file and the prepared rows are deleted. */
export function useDiscardBatch(batchId: string) {
  const queryClient = useQueryClient();
  const action = useAction(async () => {
    const batch = await api.post<Batch>(`/api/batches/${batchId}/discard`);
    queryClient.setQueryData(batchKeys.batch(batchId), batch);
    await queryClient.invalidateQueries({ queryKey: batchKeys.pending });
    return batch;
  });
  return action;
}
