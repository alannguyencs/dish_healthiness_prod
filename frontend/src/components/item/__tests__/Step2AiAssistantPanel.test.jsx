import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Step2AiAssistantPanel from "../Step2AiAssistantPanel";

describe("Step2AiAssistantPanel", () => {
  test("renders textarea and Submit disabled when value is empty", () => {
    render(
      <Step2AiAssistantPanel
        value=""
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    expect(screen.getByTestId("step2-ai-assistant-panel")).toBeInTheDocument();
    expect(screen.getByTestId("step2-ai-assistant-submit")).toBeDisabled();
  });

  test("Submit enabled when value has non-whitespace", () => {
    render(
      <Step2AiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    expect(screen.getByTestId("step2-ai-assistant-submit")).not.toBeDisabled();
  });

  test("clicking Cancel calls onCancel", () => {
    const onCancel = jest.fn();
    render(
      <Step2AiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={onCancel}
        assisting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("step2-ai-assistant-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  test("clicking Submit calls onSubmit", () => {
    const onSubmit = jest.fn();
    render(
      <Step2AiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={onSubmit}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    fireEvent.click(screen.getByTestId("step2-ai-assistant-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  test("typing calls onChange with the new value", () => {
    const onChange = jest.fn();
    render(
      <Step2AiAssistantPanel
        value=""
        onChange={onChange}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={false}
      />,
    );
    fireEvent.change(screen.getByTestId("step2-ai-assistant-textarea"), {
      target: { value: "new hint" },
    });
    expect(onChange).toHaveBeenCalledWith("new hint");
  });

  test("all controls disabled while assisting=true", () => {
    render(
      <Step2AiAssistantPanel
        value="hint"
        onChange={jest.fn()}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
        assisting={true}
      />,
    );
    expect(screen.getByTestId("step2-ai-assistant-textarea")).toBeDisabled();
    expect(screen.getByTestId("step2-ai-assistant-cancel")).toBeDisabled();
    expect(screen.getByTestId("step2-ai-assistant-submit")).toBeDisabled();
    expect(screen.getByTestId("step2-ai-assistant-submit")).toHaveTextContent(
      /Revising/i,
    );
  });
});
