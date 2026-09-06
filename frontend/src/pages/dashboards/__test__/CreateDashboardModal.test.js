import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import CreateDashboardModal from "../CreateDashboardModal";
import dashboardApi from "../../../util/dashboardApi";
import { store } from "../../../lib";

jest.mock("../../../util/dashboardApi");

// Embedding is only offered where the deployment can render it.
// `window.appConfig` is the bootstrap script in the real app.
const setEmbedEnabled = (enabled) => {
  window.appConfig = { ...(window.appConfig || {}), embedEnabled: enabled };
};

const modal = (visible, onCreate) => (
  <MemoryRouter>
    <CreateDashboardModal
      visible={visible}
      onCancel={jest.fn()}
      onCreate={onCreate}
    />
  </MemoryRouter>
);

const renderModal = (onCreate = jest.fn()) => render(modal(true, onCreate));

describe("CreateDashboardModal kind chooser", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setEmbedEnabled(true);
    store.update((s) => {
      s.allForms = [
        { id: 6001, name: "Water Points", content: { published: true } },
      ];
    });
  });

  it("offers the data source select for a built dashboard", () => {
    renderModal();
    expect(screen.getByText("Data source")).toBeInTheDocument();
  });

  it("swaps to the embed code field when embed is chosen", async () => {
    renderModal();
    await userEvent.click(screen.getByText("Embed an external dashboard"));
    expect(screen.getByText("Embed code")).toBeInTheDocument();
    expect(screen.queryByText("Data source")).not.toBeInTheDocument();
  });

  it("creates an embed with kind and snippet", async () => {
    const snippet = "<iframe src='https://app.powerbi.com/view?r=1'></iframe>";
    dashboardApi.create.mockResolvedValue({ data: { id: 1, slug: "sales" } });
    const onCreate = jest.fn();
    renderModal(onCreate);

    await userEvent.click(screen.getByText("Embed an external dashboard"));
    await userEvent.type(
      screen.getByLabelText("Dashboard name"),
      "Regional Sales"
    );
    await userEvent.type(screen.getByLabelText("Embed code"), snippet);
    await userEvent.click(screen.getByText("Create dashboard"));

    await waitFor(() =>
      expect(dashboardApi.create).toHaveBeenCalledWith({
        name: "Regional Sales",
        kind: "embed",
        embed_snippet: snippet,
      })
    );
  });

  it("shows the widgets fields again after a cancelled embed", async () => {
    // The Modal is destroyOnClose and this component is never unmounted,
    // so a second copy of the chosen kind would outlive the form reset
    // and reopen showing the embed field with a widgets form value —
    // whereupon Create posts {name, root_form: undefined} and 400s.
    const onCreate = jest.fn();
    const view = render(modal(true, onCreate));

    await userEvent.click(screen.getByText("Embed an external dashboard"));
    expect(screen.getByText("Embed code")).toBeInTheDocument();

    await userEvent.click(screen.getByText("Cancel"));
    view.rerender(modal(false, onCreate));
    await waitFor(() =>
      expect(screen.queryByText("Embed code")).not.toBeInTheDocument()
    );

    view.rerender(modal(true, onCreate));
    expect(await screen.findByText("Data source")).toBeInTheDocument();
    expect(screen.queryByText("Embed code")).not.toBeInTheDocument();
  });

  it("stays usable for an embed when the workspace has no forms", async () => {
    // The no-forms gate belongs to the widgets kind only: a workspace
    // with no forms is the one most likely to want an embed.
    store.update((s) => {
      s.allForms = [];
    });
    renderModal();
    await userEvent.click(screen.getByText("Embed an external dashboard"));
    expect(
      screen.getByText("Create dashboard").closest("button")
    ).toBeEnabled();
  });
});

describe("CreateDashboardModal without an embed host", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // EMBED_HOST unset: there is nowhere to render an embedded
    // dashboard, so creating one is not offered at all.
    setEmbedEnabled(false);
    store.update((s) => {
      s.allForms = [
        { id: 6001, name: "Water Points", content: { published: true } },
      ];
    });
  });

  it("offers no embed option", () => {
    renderModal();
    expect(
      screen.queryByText("Embed an external dashboard")
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Embed code")).not.toBeInTheDocument();
  });

  it("still offers the widgets flow", () => {
    // The gate removes a choice, not the feature underneath it: with no
    // chooser the form is the widgets form, data source and all.
    renderModal();
    expect(screen.getByText("Data source")).toBeInTheDocument();
    expect(screen.getByLabelText("Dashboard name")).toBeInTheDocument();
  });
});
