import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import FormBuilderList from "../FormBuilderList";
import { api, uiText } from "../../../lib";
import { AbilityContext, ability } from "../../../components/can";

jest.mock("../../../lib/api", () => ({
  get: jest.fn(),
  post: jest.fn(),
  token: "mock-token",
}));

jest.mock("../../../util/hooks", () => ({
  useNotification: () => ({ notify: jest.fn() }),
}));

const renderFor = async (user) => {
  render(
    <AbilityContext.Provider value={ability(user)}>
      <MemoryRouter>
        <FormBuilderList />
      </MemoryRouter>
    </AbilityContext.Provider>
  );
  await waitFor(() => expect(api.get).toHaveBeenCalled());
};

const label = uiText.en.formBuilderDataOnboardingButton;

describe("Onboard spreadsheet on the Forms list", () => {
  beforeEach(() => {
    api.get.mockResolvedValue({ data: { data: [], total: 0 } });
  });

  it("shows for a role with Data Onboarding", async () => {
    await renderFor({
      roles: [{ can_form_builder: true, can_data_onboard: true }],
    });
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("shows for a super admin", async () => {
    await renderFor({ is_superuser: true, roles: [] });
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("is hidden for a form builder role without Data Onboarding", async () => {
    await renderFor({
      roles: [{ can_form_builder: true, can_form_create: true }],
    });
    expect(screen.queryByText(label)).not.toBeInTheDocument();
    expect(
      screen.getByText(uiText.en.formBuilderImportButton)
    ).toBeInTheDocument();
  });
});
