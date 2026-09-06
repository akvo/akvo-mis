import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import DashboardVisibilityToggle from "../DashboardVisibilityToggle";

describe("DashboardVisibilityToggle", () => {
  it("is disabled while the dashboard is a draft", () => {
    render(
      <DashboardVisibilityToggle
        isPublic={false}
        isPublished={false}
        onChange={jest.fn()}
      />
    );
    expect(screen.getByRole("switch")).toBeDisabled();
  });

  it("reports the new value when toggled", async () => {
    const onChange = jest.fn();
    render(
      <DashboardVisibilityToggle
        isPublic={false}
        isPublished
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("reflects the public state", () => {
    render(
      <DashboardVisibilityToggle isPublic isPublished onChange={jest.fn()} />
    );
    expect(screen.getByRole("switch")).toBeChecked();
  });
});
