import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import ReasoningPanel from "../ReasoningPanel";

const fullStep2Data = {
  reasoning_sources: "Nutrition DB: Chicken Rice (malaysian, 88%)",
  reasoning_calories: "DB top match scaled to serving",
  reasoning_fiber: "Estimated from components",
  reasoning_carbs: "White rice drives carbs",
  reasoning_protein: "Grilled chicken component",
  reasoning_fat: "Standard oil + skin fat estimate",
  reasoning_micronutrients: "Iron + B12 from chicken",
};

describe("ReasoningPanel", () => {
  test("returns null when step2Data is missing", () => {
    const { container } = render(<ReasoningPanel step2Data={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("renders toggle, collapsed by default", () => {
    render(<ReasoningPanel step2Data={fullStep2Data} />);
    expect(screen.getByTestId("reasoning-panel-toggle")).toBeInTheDocument();
    expect(screen.queryByTestId("reasoning-panel-body")).toBeNull();
  });

  test("expand shows all seven reasoning_* fields", () => {
    render(<ReasoningPanel step2Data={fullStep2Data} />);
    fireEvent.click(screen.getByTestId("reasoning-panel-toggle"));
    expect(screen.getByTestId("reasoning-panel-body")).toBeInTheDocument();
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
      <ReasoningPanel step2Data={{ reasoning_calories: "Only calories" }} />,
    );
    fireEvent.click(screen.getByTestId("reasoning-panel-toggle"));
    expect(screen.getByTestId("reasoning-reasoning_sources")).toHaveTextContent(
      "No rationale provided",
    );
    expect(
      screen.getByTestId("reasoning-reasoning_calories"),
    ).toHaveTextContent("Only calories");
  });

  test("toggle twice collapses back", () => {
    render(<ReasoningPanel step2Data={fullStep2Data} />);
    const btn = screen.getByTestId("reasoning-panel-toggle");
    fireEvent.click(btn);
    expect(screen.getByTestId("reasoning-panel-body")).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.queryByTestId("reasoning-panel-body")).toBeNull();
  });
});
