import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import NutritionResults from "../NutritionResults";

const baseNutrition = {
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

describe("NutritionResults", () => {
  test("renders nutrition_data values when no correction present", () => {
    render(<NutritionResults nutritionData={baseNutrition} />);
    expect(screen.getByText("Chicken Rice")).toBeInTheDocument();
    expect(screen.getByText("600")).toBeInTheDocument();
    expect(
      screen.queryByTestId("nutrition-corrected-badge"),
    ).not.toBeInTheDocument();
  });

  test("renders nutrition_corrected values with badge when correction present", () => {
    const corrected = { ...baseNutrition, calories_kcal: 450 };
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        nutritionCorrected={corrected}
      />,
    );
    expect(screen.getByText("450")).toBeInTheDocument();
    expect(screen.queryByText("600")).toBeNull();
    expect(screen.getByTestId("nutrition-corrected-badge")).toBeInTheDocument();
  });

  test("Edit toggle flips into edit mode", () => {
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
      />,
    );
    expect(screen.getByTestId("nutrition-edit-toggle")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("nutrition-edit-toggle"));
    expect(screen.getByTestId("nutrition-edit-form")).toBeInTheDocument();
  });

  test("Cancel inside edit mode returns to view mode without calling onEditSave", () => {
    const onEditSave = jest.fn();
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={onEditSave}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-edit-toggle"));
    fireEvent.click(screen.getByTestId("nutrition-edit-cancel"));
    expect(screen.queryByTestId("nutrition-edit-form")).toBeNull();
    expect(onEditSave).not.toHaveBeenCalled();
  });

  test("Save calls onEditSave with the edited payload and exits edit mode", async () => {
    const onEditSave = jest.fn().mockResolvedValue({});
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={onEditSave}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-edit-toggle"));
    fireEvent.change(screen.getByTestId("nutrition-calories-input"), {
      target: { value: "450" },
    });
    fireEvent.click(screen.getByTestId("nutrition-edit-save"));
    // onEditSave called with the payload (calories override)
    expect(onEditSave).toHaveBeenCalledTimes(1);
    expect(onEditSave.mock.calls[0][0].calories_kcal).toBe(450);
  });

  test("Edit toggle hidden when onEditSave prop is not provided", () => {
    render(<NutritionResults nutritionData={baseNutrition} />);
    expect(screen.queryByTestId("nutrition-edit-toggle")).toBeNull();
  });

  test("loading state when nutritionData is null", () => {
    render(<NutritionResults nutritionData={null} />);
    expect(
      screen.getByText(/nutrition analysis in progress/i),
    ).toBeInTheDocument();
  });

  test("Stage 10 — AI Assistant button renders only when onAiAssistSubmit is provided", () => {
    const { rerender } = render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
      />,
    );
    expect(screen.queryByTestId("nutrition-ai-assistant-toggle")).toBeNull();

    rerender(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
        onAiAssistSubmit={jest.fn()}
      />,
    );
    expect(
      screen.getByTestId("nutrition-ai-assistant-toggle"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Manual Edit/i)).toBeInTheDocument();
    expect(screen.getByText(/AI Assistant Edit/i)).toBeInTheDocument();
  });

  test("Stage 10 — clicking AI Assistant toggle opens hint panel", () => {
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
        onAiAssistSubmit={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-ai-assistant-toggle"));
    expect(
      screen.getByTestId("nutrition-ai-assistant-panel"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("nutrition-ai-assistant-textarea"),
    ).toBeInTheDocument();
  });

  test("Stage 10 — Submit disabled when textarea is empty, enabled when non-empty", () => {
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
        onAiAssistSubmit={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-ai-assistant-toggle"));
    const submit = screen.getByTestId("nutrition-ai-assistant-submit");
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByTestId("nutrition-ai-assistant-textarea"), {
      target: { value: "smaller portion" },
    });
    expect(submit).not.toBeDisabled();
  });

  test("Stage 10 — Submit calls onAiAssistSubmit with trimmed hint", async () => {
    const onAiAssistSubmit = jest.fn().mockResolvedValue({});
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
        onAiAssistSubmit={onAiAssistSubmit}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-ai-assistant-toggle"));
    fireEvent.change(screen.getByTestId("nutrition-ai-assistant-textarea"), {
      target: { value: "  smaller portion  " },
    });
    fireEvent.click(screen.getByTestId("nutrition-ai-assistant-submit"));

    expect(onAiAssistSubmit).toHaveBeenCalledTimes(1);
    expect(onAiAssistSubmit.mock.calls[0][0]).toBe("smaller portion");
  });

  test("Stage 10 — both buttons disabled and AI button shows 'Revising…' while assisting", () => {
    render(
      <NutritionResults
        nutritionData={baseNutrition}
        onEditSave={jest.fn()}
        onAiAssistSubmit={jest.fn()}
        aiAssisting={true}
      />,
    );
    expect(screen.getByTestId("nutrition-edit-toggle")).toBeDisabled();
    const aiBtn = screen.getByTestId("nutrition-ai-assistant-toggle");
    expect(aiBtn).toBeDisabled();
    expect(aiBtn).toHaveTextContent(/Revising/i);
  });
});
