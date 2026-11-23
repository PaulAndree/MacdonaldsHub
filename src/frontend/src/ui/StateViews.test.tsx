import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "../api/client";
import { es } from "../i18n/es";
import {
  DeniedState,
  DiscardedState,
  EmptyState,
  ErrorState,
  IncompleteDataNotice,
  LoadingState,
  PausedState,
  PendingMarker,
} from "./StateViews";

describe("shared states", () => {
  it("loading is announced politely", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toHaveTextContent(es.common.loading);
  });

  it("empty is explicit, never a blank screen", () => {
    render(<EmptyState hint="Suba un archivo." />);
    expect(screen.getByRole("note")).toHaveTextContent(es.states.empty);
    expect(screen.getByRole("note")).toHaveTextContent("Suba un archivo.");
  });

  it("a read error is an alert with a retry action", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new NetworkError()} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(es.errors.readFailed);
    await userEvent.click(screen.getByRole("button", { name: es.common.retry }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("a failed change says the outcome is unknown and offers no automatic retry", () => {
    render(<ErrorState mutation error={new NetworkError()} onRetry={() => undefined} />);
    expect(screen.getByRole("alert")).toHaveTextContent("no sabemos si la operación se completó");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("incomplete data warns with the number of elements, and is absent when complete", () => {
    const { rerender } = render(<IncompleteDataNotice count={2} />);
    expect(screen.getByRole("note")).toHaveTextContent("Hay 2 elementos con datos incompletos");
    rerender(<IncompleteDataNotice count={1} />);
    expect(screen.getByRole("note")).toHaveTextContent("Hay 1 elemento con datos incompletos");
    rerender(<IncompleteDataNotice count={0} />);
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("permission denied is an alert", () => {
    render(<DeniedState />);
    expect(screen.getByRole("alert")).toHaveTextContent(es.states.deniedTitle);
    expect(screen.getByRole("alert")).toHaveTextContent(es.states.denied);
  });

  it("a discarded batch says it can no longer be confirmed", () => {
    render(<DiscardedState />);
    expect(screen.getByRole("status")).toHaveTextContent("ya no se puede confirmar");
  });

  it("a paused queue says an attempt already started may finish", () => {
    render(<PausedState />);
    expect(screen.getByRole("status")).toHaveTextContent("Un envío que ya había empezado puede terminar");
  });

  it("the pending-decision marker carries its P-xx identifier", () => {
    render(<PendingMarker id="P-03" />);
    expect(screen.getByText(/Pendiente de decisión \(P-03\)/)).toBeInTheDocument();
  });

  it("an API denial reads as a denial, not as a generic failure", () => {
    render(<ErrorState error={new ApiError(403, "not_authorized", "x")} />);
    expect(screen.getByRole("alert")).toHaveTextContent(es.errors.forbidden);
  });
});
