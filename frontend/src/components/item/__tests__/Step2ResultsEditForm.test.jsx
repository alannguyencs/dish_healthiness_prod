import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Step2ResultsEditForm from "../Step2ResultsEditForm";

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
    <Step2ResultsEditForm
      initialValues={{ ...baseValues, ...overrides.initialValues }}
      saving={overrides.saving || false}
      onCancel={overrides.onCancel || jest.fn()}
      onSave={overrides.onSave || jest.fn()}
    />,
  );

describe("Step2ResultsEditForm", () => {
  test("renders all editable inputs seeded with initial values", () => {
    renderForm();
    expect(screen.getByTestId("step2-healthiness-score-input")).toHaveValue(65);
    expect(screen.getByTestId("step2-rationale-input")).toHaveValue(
      "AI rationale",
    );
    expect(screen.getByTestId("step2-calories-input")).toHaveValue(600);
    expect(screen.getByTestId("step2-fiber-input")).toHaveValue(2);
    expect(screen.getByTestId("step2-carbs-input")).toHaveValue(50);
    expect(screen.getByTestId("step2-protein-input")).toHaveValue(30);
    expect(screen.getByTestId("step2-fat-input")).toHaveValue(20);
    expect(screen.getByTestId("step2-micro-chip-Iron")).toBeInTheDocument();
  });

  test("Save disabled while saving===true", () => {
    renderForm({ saving: true });
    expect(screen.getByTestId("step2-edit-save")).toBeDisabled();
  });

  test("Cancel calls onCancel", () => {
    const onCancel = jest.fn();
    renderForm({ onCancel });
    fireEvent.click(screen.getByTestId("step2-edit-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  test("micronutrient chip add + remove", () => {
    renderForm();
    const input = screen.getByTestId("step2-micro-input");
    fireEvent.change(input, { target: { value: "Magnesium" } });
    fireEvent.click(screen.getByTestId("step2-micro-add"));
    expect(
      screen.getByTestId("step2-micro-chip-Magnesium"),
    ).toBeInTheDocument();
    // Remove
    const chip = screen.getByTestId("step2-micro-chip-Magnesium");
    fireEvent.click(chip.querySelector("button"));
    expect(screen.queryByTestId("step2-micro-chip-Magnesium")).toBeNull();
  });

  test("Save packages values into payload and calls onSave", () => {
    const onSave = jest.fn();
    renderForm({ onSave });
    fireEvent.change(screen.getByTestId("step2-calories-input"), {
      target: { value: "450" },
    });
    fireEvent.click(screen.getByTestId("step2-edit-save"));
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
    expect(screen.getByTestId("step2-micro-chip-Iron")).toBeInTheDocument();
    expect(screen.getByTestId("step2-micro-chip-Folate")).toBeInTheDocument();
  });
});
