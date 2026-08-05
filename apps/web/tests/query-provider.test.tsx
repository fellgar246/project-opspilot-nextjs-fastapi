import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QueryProvider } from "@/features/incidents/QueryProvider";

describe("QueryProvider", () => {
  it("renders children", () => {
    render(
      <QueryProvider>
        <p>child content</p>
      </QueryProvider>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });
});
