import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import Top5DbMatches from "../Top5DbMatches";

const match = (name, score, source = "malaysian_food_calories") => ({
  matched_food_name: name,
  source,
  confidence_score: score,
});

describe("Top5DbMatches", () => {
  test("returns null when matches is empty", () => {
    const { container } = render(<Top5DbMatches matches={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("returns null when matches is undefined", () => {
    const { container } = render(<Top5DbMatches />);
    expect(container).toBeEmptyDOMElement();
  });

  test("renders up to 5 chips", () => {
    const matches = Array.from({ length: 10 }).map((_, i) =>
      match(`Dish ${i}`, 90 - i),
    );
    render(<Top5DbMatches matches={matches} />);
    expect(screen.getByTestId("db-match-chip-0")).toBeInTheDocument();
    expect(screen.getByTestId("db-match-chip-4")).toBeInTheDocument();
    expect(screen.queryByTestId("db-match-chip-5")).toBeNull();
  });

  test("confidence score rounds + renders as percent", () => {
    render(<Top5DbMatches matches={[match("Chicken Rice", 87.6)]} />);
    expect(screen.getByText("88%")).toBeInTheDocument();
  });

  test("renders the match name verbatim", () => {
    render(<Top5DbMatches matches={[match("Nasi Lemak", 90)]} />);
    expect(screen.getByText("Nasi Lemak")).toBeInTheDocument();
  });
});
