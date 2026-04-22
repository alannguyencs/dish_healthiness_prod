import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import ReasoningPanel from "../ReasoningPanel";

const fullNutritionData = {
  reasoning_sources: "Nutrition DB: Chicken Rice (malaysian, 88%)",
  reasoning_calories: "DB top match scaled to serving",
  reasoning_fiber: "Estimated from components",
  reasoning_carbs: "White rice drives carbs",
  reasoning_protein: "Grilled chicken component",
  reasoning_fat: "Standard oil + skin fat estimate",
  reasoning_micronutrients: "Iron + B12 from chicken",
};

describe("ReasoningPanel", () => {
  test("returns null when nutritionData is missing", () => {
    const { container } = render(<ReasoningPanel nutritionData={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("renders the body non-conditionally when nutritionData is present", () => {
    // Open/close is owned by the outer <ResearchOnlyGroup> now, not by
    // this panel — the body always renders when nutritionData is present.
    render(<ReasoningPanel nutritionData={fullNutritionData} />);
    expect(screen.getByTestId("reasoning-panel")).toBeInTheDocument();
    expect(screen.getByTestId("reasoning-panel-body")).toBeInTheDocument();
    expect(screen.queryByTestId("reasoning-panel-toggle")).toBeNull();
  });

  test("renders all seven reasoning_* fields", () => {
    render(<ReasoningPanel nutritionData={fullNutritionData} />);
    expect(screen.getByTestId("reasoning-reasoning_sources")).toHaveTextContent(
      "Nutrition DB",
    );
    expect(
      screen.getByTestId("reasoning-reasoning_calories"),
    ).toHaveTextContent("DB top match");
    expect(
      screen.getByTestId("reasoning-reasoning_micronutrients"),
    ).toHaveTextContent("Iron + B12");
  });

  test("empty reasoning fields render as 'No rationale provided'", () => {
    render(
      <ReasoningPanel
        nutritionData={{ reasoning_calories: "Only calories" }}
      />,
    );
    expect(screen.getByTestId("reasoning-reasoning_sources")).toHaveTextContent(
      "No rationale provided",
    );
    expect(
      screen.getByTestId("reasoning-reasoning_calories"),
    ).toHaveTextContent("Only calories");
  });
});
