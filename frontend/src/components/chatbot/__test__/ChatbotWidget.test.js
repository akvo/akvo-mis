import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { store } from "../../../lib";
import ChatbotWidget from "../ChatbotWidget";

// Mock axios / api
jest.mock("../../../lib", () => {
  const actual = jest.requireActual("../../../lib");
  return {
    ...actual,
    api: {
      post: jest.fn(() =>
        Promise.resolve({
          data: {
            response: "Mocked AI answer",
            thread_id: "thread_test_123",
          },
        })
      ),
    },
  };
});

describe("ChatbotWidget", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = jest.fn();
    store.update((s) => {
      s.user = { id: 1, email: "tester@akvo.org", role: "admin" };
    });
  });

  test("renders FAB button and expands panel on click", () => {
    render(
      <BrowserRouter>
        <ChatbotWidget />
      </BrowserRouter>
    );

    // Find FAB button by aria-label
    const fab = screen.getByRole("button", { name: /Open AI Assistant/i });
    expect(fab).toBeInTheDocument();

    // Click to open panel
    fireEvent.click(fab);

    // Header should show Mira and MIS Assistant
    expect(screen.getByText("Mira")).toBeInTheDocument();
    expect(screen.getByText("MIS Assistant")).toBeInTheDocument();
    expect(screen.getAllByText("General Platform").length).toBeGreaterThan(0);

    // Empty state welcome text
    expect(screen.getByText(/Hi! I'm Mira/i)).toBeInTheDocument();
    expect(
      screen.getByText(/What can I do on this page\?/i)
    ).toBeInTheDocument();
  });
});
