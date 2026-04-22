import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import NutritionAiAssistantPanel from "../NutritionAiAssistantPanel";

describe("NutritionAiAssistantPanel", () => {
  test("renders textarea and Submit disabled when value is empty", () => {
    render(
      <NutritionAiAssistantPanel
        value=""
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    expect(
      screen.getByTestId("nutrition-ai-assistant-panel"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("nutrition-ai-assistant-submit")).toBeDisabled();
  });

  test("Submit enabled when value has non-whitespace", () => {
    render(
      <NutritionAiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    expect(
      screen.getByTestId("nutrition-ai-assistant-submit"),
    ).not.toBeDisabled();
  });

  test("clicking Cancel calls onCancel", () => {
    const onCancel = jest.fn();
    render(
      <NutritionAiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={onCancel}
        assisting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-ai-assistant-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  test("clicking Submit calls onSubmit", () => {
    const onSubmit = jest.fn();
    render(
      <NutritionAiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={onSubmit}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("nutrition-ai-assistant-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  test("typing calls onChange with the new value", () => {
    const onChange = jest.fn();
    render(
      <NutritionAiAssistantPanel
        value=""
        onChange={onChange}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    fireEvent.change(screen.getByTestId("nutrition-ai-assistant-textarea"), {
      target: { value: "new hint" },
    });
    expect(onChange).toHaveBeenCalledWith("new hint");
  });

  test("all controls disabled while assisting=true", () => {
    render(
      <NutritionAiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={true}
      />,
    );
    expect(
      screen.getByTestId("nutrition-ai-assistant-textarea"),
    ).toBeDisabled();
    expect(screen.getByTestId("nutrition-ai-assistant-cancel")).toBeDisabled();
    expect(screen.getByTestId("nutrition-ai-assistant-submit")).toBeDisabled();
    expect(
      screen.getByTestId("nutrition-ai-assistant-submit"),
    ).toHaveTextContent(/Revising/i);
  });
});
