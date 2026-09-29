import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import RenameModal from "../RenameModal";
import "@testing-library/jest-dom";

jest.mock("axios");

const tenant = { id: 42, subdomain: "mohhs" };
const impact = {
  published_dashboards: 3,
  public_dashboards: 2,
};

const dialog = (props = {}) => (
  <RenameModal
    tenant={tenant}
    open
    onClose={() => {}}
    onRenamed={() => {}}
    {...props}
  />
);

let rerender;

const open = async (mock, props = {}) => {
  axios.mockImplementation(mock);
  await act(async () => {
    ({ rerender } = render(dialog(props)));
  });
};

const resolveImpact = () => Promise.resolve({ status: 200, data: impact });

const type = async (field, value) => {
  await act(async () => {
    fireEvent.change(field, { target: { value } });
  });
};

const confirmButton = () =>
  screen.getByRole("button", { name: /rename workspace/i });

describe("Rename dialog", () => {
  it("states the impact as live counts", async () => {
    await open(resolveImpact);
    expect(screen.getByText(/3 dashboard links/)).toBeInTheDocument();
    expect(
      screen.getByText(/2 publicly shared dashboards/)
    ).toBeInTheDocument();
  });

  it("does not claim mobile devices break", async () => {
    // They do not. The app syncs against the deployment's own address,
    // never a workspace's, and its data is partitioned by the token's
    // assignment rather than by the host — so a rename leaves every
    // enrolled device working. This was the dialog's most alarming
    // line and it described field work that does not exist.
    await open(resolveImpact);
    expect(screen.queryByText(/device/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/syncing/i)).not.toBeInTheDocument();
  });

  it("does not claim embedded dashboards break", async () => {
    // They do not. The embed document is served from EMBED_HOST under a
    // signed token carrying a dashboard id, so a rename leaves its URL
    // untouched — and a dialog that names a consequence which does not
    // happen spends the credibility the real counts are for.
    await open(resolveImpact);
    expect(screen.queryByText(/embedded/i)).not.toBeInTheDocument();
  });

  it("keeps confirm disabled until the subdomain is typed", async () => {
    await open(resolveImpact);
    expect(confirmButton()).toBeDisabled();
    await type(screen.getByLabelText(/new address/i), "moh");
    await type(screen.getByLabelText(/to confirm/i), "mohhs");
    expect(confirmButton()).not.toBeDisabled();
  });

  it("stays disabled with no new address to rename to", async () => {
    // Typing the confirmation alone would otherwise arm a POST whose
    // subdomain is the empty string, which the backend answers with a
    // 400 the operator has no way to interpret.
    await open(resolveImpact);
    await type(screen.getByLabelText(/to confirm/i), "mohhs");
    expect(confirmButton()).toBeDisabled();
  });

  it("stays disabled when the confirmation does not match", async () => {
    // Without this the typed confirmation is decoration: the dialog
    // would arm on any text at all, including none.
    await open(resolveImpact);
    await type(screen.getByLabelText(/new address/i), "moh");
    await type(screen.getByLabelText(/to confirm/i), "mohs");
    expect(confirmButton()).toBeDisabled();
  });

  it("posts the new address and hands the workspace back", async () => {
    const onRenamed = jest.fn();
    const onClose = jest.fn();
    await open(resolveImpact, { onRenamed, onClose });
    await type(screen.getByLabelText(/new address/i), "moh-new");
    await type(screen.getByLabelText(/to confirm/i), "mohhs");
    axios.mockResolvedValue({
      status: 200,
      data: { ...tenant, subdomain: "moh-new" },
    });
    await act(async () => {
      userEvent.click(confirmButton());
    });
    const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
    expect(call[0].url).toBe("admin/tenants/42/rename");
    // The new address, not the confirmation. They are different fields
    // and posting the wrong one would rename nothing and look fine.
    expect(call[0].data).toEqual({ subdomain: "moh-new" });
    expect(onRenamed).toHaveBeenCalledWith(
      expect.objectContaining({ subdomain: "moh-new" })
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("forgets what was typed when it is closed and reopened", async () => {
    // The dialog is mounted permanently by TenantDetail, so its state
    // outlives a Cancel. An operator who typed the confirmation and
    // then thought better of it would find the danger-red button
    // already armed next time they opened it to read the impact — one
    // click from a rename they came to reconsider.
    await open(resolveImpact);
    await type(screen.getByLabelText(/new address/i), "moh-new");
    await type(screen.getByLabelText(/to confirm/i), "mohhs");
    expect(confirmButton()).not.toBeDisabled();

    await act(async () => {
      rerender(dialog({ open: false }));
    });
    await act(async () => {
      rerender(dialog({ open: true }));
    });

    expect(screen.getByLabelText(/new address/i)).toHaveValue("");
    expect(screen.getByLabelText(/to confirm/i)).toHaveValue("");
    expect(confirmButton()).toBeDisabled();
  });

  it("stays disabled when the impact cannot be loaded", async () => {
    // Failing open here would let someone rename a workspace without
    // seeing what it breaks, which is the one thing this dialog exists
    // to prevent.
    await open(() => Promise.reject(new Error("offline")));
    await type(screen.getByLabelText(/new address/i), "moh");
    await type(screen.getByLabelText(/to confirm/i), "mohhs");
    expect(confirmButton()).toBeDisabled();
  });
});
