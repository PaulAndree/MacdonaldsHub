import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import { DeniedState, EmptyState, ErrorState, LoadingState } from "./StateViews";

interface QueryViewProps<T> {
  query: UseQueryResult<T>;
  /** When true for the loaded data, the empty state is shown instead of the children. */
  isEmpty?: (data: T) => boolean;
  emptyTitle?: string;
  children: (data: T) => ReactNode;
}

/** Loading, error, denied and empty states for one query, then the data. */
export default function QueryView<T>({ query, isEmpty, emptyTitle, children }: QueryViewProps<T>) {
  if (query.isPending) return <LoadingState />;
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 403) return <DeniedState />;
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (isEmpty?.(query.data)) return <EmptyState title={emptyTitle} />;
  return <>{children(query.data)}</>;
}
