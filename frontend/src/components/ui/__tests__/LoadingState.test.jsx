/**
 * LoadingState — platform-standard loading-before-data indicator.
 *
 * Guards the shared contract every converted page now relies on:
 *   1. role="status" + localized aria-label on every variant.
 *   2. fullpage variant shows a visible localized label by default.
 *   3. section/inline variants show no visible label unless one is passed.
 *   4. Extra props (data-testid, className) pass through to the root.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "../../../contexts/ThemeContext";
import { LoadingState } from "../LoadingState";

const renderWithTheme = (ui) => render(<ThemeProvider>{ui}</ThemeProvider>);

describe("LoadingState", () => {
  test("default (section) renders role=status with localized aria-label and no visible text", () => {
    renderWithTheme(<LoadingState data-testid="ls" />);
    const root = screen.getByTestId("ls");
    expect(root).toHaveAttribute("role", "status");
    expect(root.getAttribute("aria-label")).toBeTruthy();
    expect(root.querySelector("p")).toBeNull();
    expect(root.querySelector("svg.animate-spin")).toBeInTheDocument();
  });

  test("fullpage variant shows a visible default label", () => {
    renderWithTheme(<LoadingState variant="fullpage" data-testid="ls" />);
    const root = screen.getByTestId("ls");
    const label = root.querySelector("p");
    expect(label).toBeInTheDocument();
    expect(label.textContent.length).toBeGreaterThan(0);
    expect(root.getAttribute("aria-label")).toBe(label.textContent);
  });

  test("custom label is rendered and used as aria-label", () => {
    renderWithTheme(<LoadingState label="جاري تحميل البيانات..." data-testid="ls" />);
    const root = screen.getByTestId("ls");
    expect(screen.getByText("جاري تحميل البيانات...")).toBeInTheDocument();
    expect(root.getAttribute("aria-label")).toBe("جاري تحميل البيانات...");
  });

  test("className and extra props pass through to the root element", () => {
    renderWithTheme(<LoadingState className="my-custom" data-testid="ls" />);
    const root = screen.getByTestId("ls");
    expect(root.classList.contains("my-custom")).toBe(true);
  });
});
