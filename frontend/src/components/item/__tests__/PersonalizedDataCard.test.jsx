import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...rest }) => (
      <a href={to} {...rest}>
        {children}
      </a>
    ),
  }),
  { virtual: true },
);

// Import AFTER the mock so the component picks up the mocked Link.
// eslint-disable-next-line import/first
import PersonalizedDataCard from "../PersonalizedDataCard";

const REFERENCE = {
  query_id: 42,
  image_url: "/images/prior.jpg",
  description: "grilled chicken rice with cucumber",
  similarity_score: 0.72,
  prior_step1_data: null,
};

const renderCard = (props) => render(<PersonalizedDataCard {...props} />);

describe("PersonalizedDataCard", () => {
  test("renders header but hides body by default", () => {
    renderCard({ flashCaption: "a plate of food", referenceImage: REFERENCE });
    expect(
      screen.getByText(/Personalized Data \(Research only\)/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("personalized-data-flash-caption"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("personalized-data-reference"),
    ).not.toBeInTheDocument();
  });

  test("clicking toggle reveals body with flash caption and reference", async () => {
    renderCard({
      flashCaption: "golden-brown fried chicken on a plate",
      referenceImage: REFERENCE,
    });
    await userEvent.click(screen.getByTestId("personalized-data-toggle"));

    expect(
      screen.getByTestId("personalized-data-flash-caption"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/golden-brown fried chicken on a plate/),
    ).toBeInTheDocument();

    const refSection = screen.getByTestId("personalized-data-reference");
    expect(refSection).toBeInTheDocument();
    expect(refSection).toHaveTextContent(/Query #42/);
    expect(refSection).toHaveTextContent(/0\.72 sim/);
    expect(refSection).toHaveTextContent(/grilled chicken rice with cucumber/);
    expect(refSection.querySelector("a[href='/item/42']")).toBeInTheDocument();
    expect(refSection.querySelector("img")).toHaveAttribute(
      "src",
      "/images/prior.jpg",
    );
  });

  test("falls back when flashCaption is null", async () => {
    renderCard({ flashCaption: null, referenceImage: REFERENCE });
    await userEvent.click(screen.getByTestId("personalized-data-toggle"));
    const flash = screen.getByTestId("personalized-data-flash-caption");
    expect(flash).toHaveTextContent(/No caption generated/i);
  });

  test("falls back when referenceImage is null", async () => {
    renderCard({ flashCaption: "some caption", referenceImage: null });
    await userEvent.click(screen.getByTestId("personalized-data-toggle"));
    const ref = screen.getByTestId("personalized-data-reference");
    expect(ref).toHaveTextContent(/No prior match/i);
    expect(ref.querySelector("a[href^='/item/']")).not.toBeInTheDocument();
  });

  test("toggling again collapses the body", async () => {
    renderCard({ flashCaption: "x", referenceImage: REFERENCE });
    const toggle = screen.getByTestId("personalized-data-toggle");
    await userEvent.click(toggle);
    expect(
      screen.getByTestId("personalized-data-flash-caption"),
    ).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(
      screen.queryByTestId("personalized-data-flash-caption"),
    ).not.toBeInTheDocument();
  });
});
