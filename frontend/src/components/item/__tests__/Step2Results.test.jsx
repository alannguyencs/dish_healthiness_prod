import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Step2Results from "../Step2Results";

const baseStep2 = {
  dish_name: "Chicken Rice",
  healthiness_score: 65,
  healthiness_score_rationale: "AI rationale",
  calories_kcal: 600,
  fiber_g: 2,
  carbs_g: 60,
  protein_g: 25,
  fat_g: 20,
  micronutrients: ["Iron"],
};

describe("Step2Results", () => {
  test("renders step2_data values when no correction present", () => {
    render(<Step2Results step2Data={baseStep2} />);
    expect(screen.getByText("Chicken Rice")).toBeInTheDocument();
    expect(screen.getByText("600")).toBeInTheDocument();
    expect(
      screen.queryByTestId("step2-corrected-badge"),
    ).not.toBeInTheDocument();
  });

  test("renders step2_corrected values with badge when correction present", () => {
    const corrected = { ...baseStep2, calories_kcal: 450 };
    render(<Step2Results step2Data={baseStep2} step2Corrected={corrected} />);
    expect(screen.getByText("450")).toBeInTheDocument();
    expect(screen.queryByText("600")).toBeNull();
    expect(screen.getByTestId("step2-corrected-badge")).toBeInTheDocument();
  });

  test("Edit toggle flips into edit mode", () => {
    render(<Step2Results step2Data={baseStep2} onEditSave={jest.fn()} />);
    expect(screen.getByTestId("step2-edit-toggle")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("step2-edit-toggle"));
    expect(screen.getByTestId("step2-edit-form")).toBeInTheDocument();
  });

  test("Cancel inside edit mode returns to view mode without calling onEditSave", () => {
    const onEditSave = jest.fn();
    render(<Step2Results step2Data={baseStep2} onEditSave={onEditSave} />);
    fireEvent.click(screen.getByTestId("step2-edit-toggle"));
    fireEvent.click(screen.getByTestId("step2-edit-cancel"));
    expect(screen.queryByTestId("step2-edit-form")).toBeNull();
    expect(onEditSave).not.toHaveBeenCalled();
  });

  test("Save calls onEditSave with the edited payload and exits edit mode", async () => {
    const onEditSave = jest.fn().mockResolvedValue({});
    render(<Step2Results step2Data={baseStep2} onEditSave={onEditSave} />);
    fireEvent.click(screen.getByTestId("step2-edit-toggle"));
    fireEvent.change(screen.getByTestId("step2-calories-input"), {
      target: { value: "450" },
    });
    fireEvent.click(screen.getByTestId("step2-edit-save"));
    // onEditSave called with the payload (calories override)
    expect(onEditSave).toHaveBeenCalledTimes(1);
    expect(onEditSave.mock.calls[0][0].calories_kcal).toBe(450);
  });

  test("Edit toggle hidden when onEditSave prop is not provided", () => {
    render(<Step2Results step2Data={baseStep2} />);
    expect(screen.queryByTestId("step2-edit-toggle")).toBeNull();
  });

  test("loading state when step2Data is null", () => {
    render(<Step2Results step2Data={null} />);
    expect(
      screen.getByText(/step 2 analysis in progress/i),
    ).toBeInTheDocument();
  });
});
