import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import NutritionResultsEditForm from "../NutritionResultsEditForm";

const baseValues = {
  healthiness_score: 65,
  healthiness_score_rationale: "AI rationale",
  calories_kcal: 600,
  fiber_g: 2,
  carbs_g: 50,
  protein_g: 30,
  fat_g: 20,
  micronutrients: ["Iron", "Vitamin C"],
};

const renderForm = (overrides = {}) =>
  render(
    <NutritionResultsEditForm
      initialValues={{ ...baseValues, ...overrides.initialValues }}
      saving={overrides.saving || false}
      onCancel={overrides.onCancel || jest.fn()}
      onSave={overrides.onSave || jest.fn()}
    />,
  );

describe("NutritionResultsEditForm", () => {
  test("renders all editable inputs seeded with initial values", () => {
    renderForm();
    expect(
      screen.getByTestId("nutrition-healthiness-score-input"),
    ).toHaveValue(65);
    expect(screen.getByTestId("nutrition-rationale-input")).toHaveValue(
      "AI rationale",
    );
    expect(screen.getByTestId("nutrition-calories-input")).toHaveValue(600);
    expect(screen.getByTestId("nutrition-fiber-input")).toHaveValue(2);
    expect(screen.getByTestId("nutrition-carbs-input")).toHaveValue(50);
    expect(screen.getByTestId("nutrition-protein-input")).toHaveValue(30);
    expect(screen.getByTestId("nutrition-fat-input")).toHaveValue(20);
    expect(screen.getByTestId("nutrition-micro-chip-Iron")).toBeInTheDocument();
  });

  test("Save disabled while saving===true", () => {
    renderForm({ saving: true });
    expect(screen.getByTestId("nutrition-edit-save")).toBeDisabled();
  });

  test("Cancel calls onCancel", () => {
    const onCancel = jest.fn();
    renderForm({ onCancel });
    fireEvent.click(screen.getByTestId("nutrition-edit-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  test("micronutrient chip add + remove", () => {
    renderForm();
    const input = screen.getByTestId("nutrition-micro-input");
    fireEvent.change(input, { target: { value: "Magnesium" } });
    fireEvent.click(screen.getByTestId("nutrition-micro-add"));
    expect(
      screen.getByTestId("nutrition-micro-chip-Magnesium"),
    ).toBeInTheDocument();
    // Remove
    const chip = screen.getByTestId("nutrition-micro-chip-Magnesium");
    fireEvent.click(chip.querySelector("button"));
    expect(screen.queryByTestId("nutrition-micro-chip-Magnesium")).toBeNull();
  });

  test("Save packages values into payload and calls onSave", () => {
    const onSave = jest.fn();
    renderForm({ onSave });
    fireEvent.change(screen.getByTestId("nutrition-calories-input"), {
      target: { value: "450" },
    });
    fireEvent.click(screen.getByTestId("nutrition-edit-save"));
    expect(onSave).toHaveBeenCalledTimes(1);
    const payload = onSave.mock.calls[0][0];
    expect(payload.calories_kcal).toBe(450);
    expect(payload.healthiness_score).toBe(65);
    expect(payload.micronutrients).toEqual(["Iron", "Vitamin C"]);
  });

  test("normalizes object-shaped micronutrients to plain strings", () => {
    renderForm({
      initialValues: {
        micronutrients: [{ name: "Iron", amount_mg: 5 }, "Folate"],
      },
    });
    expect(screen.getByTestId("nutrition-micro-chip-Iron")).toBeInTheDocument();
    expect(
      screen.getByTestId("nutrition-micro-chip-Folate"),
    ).toBeInTheDocument();
  });
});
