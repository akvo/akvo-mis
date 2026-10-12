import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Modal } from "antd";
import axios from "axios";
import Operators from "../Operators";
import "@testing-library/jest-dom";

jest.mock("axios");

const operators = [
  {
    id: 1,
    name: "Zuhdil Herry Kurnia",
    email: "zuhdil@akvo.org",
    state: "active",
    date_joined: null,
    last_login: null,
  },
  {
    id: 2,
    name: "",
    email: "wayan@akvo.org",
    state: "pending",
    date_joined: null,
    last_login: null,
  },
];

const renderPage = async () => {
  axios.mockResolvedValue({ status: 200, data: operators });
  await act(async () => {
    render(
      <MemoryRouter>
        <Operators />
      </MemoryRouter>
    );
  });
};

describe("Operators", () => {
  // Modal.confirm renders into document.body, outside the container
  // Testing Library unmounts, so a dialog left open by one test would
  // still be on screen in the next.
  afterEach(() => {
    Modal.destroyAll();
    document.body.innerHTML = "";
  });

  it("lists operators and their state", async () => {
    await renderPage();
    expect(screen.getByText("zuhdil@akvo.org")).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });

  it("invites a peer", async () => {
    await renderPage();
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /invite operator/i }));
    });
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: "dedi@akvo.org" },
      });
    });
    axios.mockClear();
    axios.mockResolvedValue({ status: 200, data: operators });
    await act(async () => {
      userEvent.click(screen.getByRole("button", { name: /^invite$/i }));
    });
    const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
    expect(call[0].data.email).toBe("dedi@akvo.org");
  });

  it("asks before revoking, and does not revoke on opening the dialog", async () => {
    await renderPage();
    axios.mockClear();
    await act(async () => {
      userEvent.click(screen.getAllByRole("button", { name: /revoke/i })[0]);
    });
    expect(
      await screen.findByText(/lose console access immediately/i)
    ).toBeInTheDocument();
    expect(
      axios.mock.calls.find(([conf]) => conf.method === "DELETE")
    ).toBeUndefined();
  });
});
