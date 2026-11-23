import type { ReactNode } from "react";
import contract from "./contract.json";
import ScenarioPanel from "./ScenarioPanel";
import { exampleEs } from "./strings";

/** Permanent notice: every screen of the example build says its data is not real. */
export function ExampleBanner() {
  return (
    <div className="banner banner--example" role="note">
      {exampleEs.banner}
    </div>
  );
}

/** Design version (a git tag) and contract version under review. */
export function ExampleFooter() {
  const design = import.meta.env.VITE_DESIGN_VERSION || exampleEs.footer.unreleased;
  return (
    <>
      <ScenarioPanel />
      <p>
        {exampleEs.footer.designVersion}: <strong>{design}</strong> · {exampleEs.footer.contractVersion}{" "}
        <strong>{contract.info.version}</strong>
      </p>
    </>
  );
}

export interface ExampleUi {
  banner: ReactNode;
  footer: ReactNode;
}

export const exampleUi: ExampleUi = {
  banner: <ExampleBanner />,
  footer: <ExampleFooter />,
};
