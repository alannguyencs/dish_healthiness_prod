import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import ResearchOnlyGroup from "../ResearchOnlyGroup";

describe("ResearchOnlyGroup", () => {
  test("renders the header label but hides children by default", () => {
    render(
      <ResearchOnlyGroup>
        <div data-testid="child-a">A</div>
        <div data-testid="child-b">B</div>
      </ResearchOnlyGroup>,
    );
    expect(screen.getByTestId("research-only-group")).toBeInTheDocument();
    expect(screen.getByTestId("research-only-toggle")).toBeInTheDocument();
    expect(screen.getByText(/Research only/i)).toBeInTheDocument();
    expect(screen.queryByTestId("research-only-body")).not.toBeInTheDocument();
    expect(screen.queryByTestId("child-a")).not.toBeInTheDocument();
    expect(screen.queryByTestId("child-b")).not.toBeInTheDocument();
  });

  test("clicking the toggle reveals children", async () => {
    render(
      <ResearchOnlyGroup>
        <div data-testid="child-a">A</div>
        <div data-testid="child-b">B</div>
      </ResearchOnlyGroup>,
    );
    await userEvent.click(screen.getByTestId("research-only-toggle"));
    expect(screen.getByTestId("research-only-body")).toBeInTheDocument();
    expect(screen.getByTestId("child-a")).toBeInTheDocument();
    expect(screen.getByTestId("child-b")).toBeInTheDocument();
  });

  test("clicking the toggle again collapses the body", async () => {
    render(
      <ResearchOnlyGroup>
        <div data-testid="child-a">A</div>
      </ResearchOnlyGroup>,
    );
    const toggle = screen.getByTestId("research-only-toggle");
    await userEvent.click(toggle);
    expect(screen.getByTestId("child-a")).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.queryByTestId("child-a")).not.toBeInTheDocument();
  });

  test("aria-expanded reflects the collapse state", async () => {
    render(
      <ResearchOnlyGroup>
        <div data-testid="child-a">A</div>
      </ResearchOnlyGroup>,
    );
    const toggle = screen.getByTestId("research-only-toggle");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});
