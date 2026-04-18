import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import PhaseErrorCard from "../PhaseErrorCard";

const baseError = {
  error_type: "api_error",
  message: "The nutrition service is temporarily unavailable.",
  occurred_at: "2026-04-18T12:00:00+00:00",
  retry_count: 0,
};

const renderCard = (overrides = {}) =>
  render(
    <PhaseErrorCard
      headline={overrides.headline || "Nutritional analysis failed"}
      error={{ ...baseError, ...overrides.error }}
      onRetry={overrides.onRetry || jest.fn()}
      isRetrying={overrides.isRetrying || false}
    />,
  );

describe("PhaseErrorCard", () => {
  test("renders the user-facing message", () => {
    renderCard();
    expect(
      screen.getByText("The nutrition service is temporarily unavailable."),
    ).toBeInTheDocument();
  });

  test("renders the headline prop", () => {
    renderCard({ headline: "Component identification failed" });
    expect(
      screen.getByText("Component identification failed"),
    ).toBeInTheDocument();
  });

  test("calls onRetry when Try Again is clicked", () => {
    const onRetry = jest.fn();
    renderCard({ onRetry });
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  test("disables button and shows Retrying... while in flight", () => {
    renderCard({ isRetrying: true });
    const btn = screen.getByRole("button", { name: /retrying/i });
    expect(btn).toBeDisabled();
  });

  test("hides retry button entirely for config_error", () => {
    renderCard({ error: { error_type: "config_error" } });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("shows soft cap warning + Try Anyway label after 5 attempts", () => {
    renderCard({ error: { retry_count: 5 } });
    expect(screen.getByText(/we.*tried 5 times/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try anyway/i }),
    ).toBeInTheDocument();
  });

  test("shows Previous attempts footer once retry_count > 0", () => {
    renderCard({ error: { retry_count: 2 } });
    expect(screen.getByText(/previous attempts: 2/i)).toBeInTheDocument();
  });

  test("returns null when error is missing", () => {
    const { container } = render(
      <PhaseErrorCard
        headline="x"
        error={null}
        onRetry={jest.fn()}
        isRetrying={false}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
