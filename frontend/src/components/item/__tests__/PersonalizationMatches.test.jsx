import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import PersonalizationMatches from "../PersonalizationMatches";

const match = ({
  query_id = 42,
  description = "chicken rice",
  similarity_score = 0.55,
  prior = null,
  corrected = null,
  image_url = "/images/prior.jpg",
} = {}) => ({
  query_id,
  image_url,
  description,
  similarity_score,
  prior_step2_data: prior,
  corrected_step2_data: corrected,
});

const PRIOR = {
  calories_kcal: 480,
  fiber_g: 2,
  carbs_g: 55,
  protein_g: 22,
  fat_g: 14,
};

const CORRECTED = {
  calories_kcal: 420,
  fiber_g: 3,
  carbs_g: 50,
  protein_g: 25,
  fat_g: 10,
};

describe("PersonalizationMatches", () => {
  test("returns null when matches is empty", () => {
    const { container } = render(<PersonalizationMatches matches={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("renders one card per match with thumbnail + description + similarity", () => {
    render(
      <PersonalizationMatches
        matches={[match({ query_id: 7, prior: PRIOR })]}
      />,
    );
    expect(screen.getByTestId("persona-card-7")).toBeInTheDocument();
    expect(screen.getByText("chicken rice")).toBeInTheDocument();
    expect(screen.getByText("55% similar")).toBeInTheDocument();
    // Component prefixes relative paths with the backend base URL so the
    // thumbnail hits FastAPI on port 2612 instead of 404ing against the
    // React dev server on port 2512.
    expect(screen.getByRole("img").getAttribute("src")).toMatch(
      /\/images\/prior\.jpg$/,
    );
  });

  test("shows corrected macros with User-verified badge when corrected_step2_data set", () => {
    render(
      <PersonalizationMatches
        matches={[match({ query_id: 7, prior: PRIOR, corrected: CORRECTED })]}
      />,
    );
    expect(screen.getByTestId("persona-user-verified-7")).toBeInTheDocument();
    // Corrected calories (420) rendered, not prior 480
    expect(screen.getByText("420")).toBeInTheDocument();
    expect(screen.queryByText("480")).toBeNull();
  });

  test("shows prior macros without badge when corrected is null", () => {
    render(
      <PersonalizationMatches
        matches={[match({ query_id: 7, prior: PRIOR, corrected: null })]}
      />,
    );
    expect(screen.queryByTestId("persona-user-verified-7")).toBeNull();
    expect(screen.getByText("480")).toBeInTheDocument();
  });

  test("handles match with neither prior nor corrected gracefully", () => {
    render(
      <PersonalizationMatches
        matches={[match({ query_id: 7, prior: null, corrected: null })]}
      />,
    );
    // Card still renders; macros section is empty but does not crash
    expect(screen.getByTestId("persona-card-7")).toBeInTheDocument();
  });
});
