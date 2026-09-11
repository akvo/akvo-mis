import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import ImportFormModal from "../ImportFormModal";
import uiText from "../../../../lib/ui-text";
import { api } from "../../../../lib";

jest.mock("../../../../lib", () => {
  const actual = jest.requireActual("../../../../lib");
  return {
    ...actual,
    api: {
      get: jest.fn(),
      post: jest.fn(),
    },
  };
});

describe("ImportFormModal XLSForm Review Messaging", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("displays the exact XLSForm review guidance banner during review step", async () => {
    api.post.mockResolvedValueOnce({
      data: {
        form: { name: "Kobo Survey Form" },
        question_count: 8,
        group_count: 2,
        skipped_count: 0,
        warnings: [],
      },
    });

    render(
      <MemoryRouter>
        <ImportFormModal
          open={true}
          onClose={jest.fn()}
          onImported={jest.fn()}
          text={uiText.en}
        />
      </MemoryRouter>
    );

    // Switch to XLSForm format
    const xlsOption = screen.getByLabelText(/XLSForm/i);
    fireEvent.click(xlsOption);

    // Upload an xlsx file
    const file = new File(["dummy content"], "survey.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const uploadInput = document.querySelector('input[type="file"]');
    fireEvent.change(uploadInput, { target: { files: [file] } });

    // Wait for preflight to resolve and review screen to show
    await waitFor(() => {
      expect(
        screen.getByText("This import needs a quick review")
      ).toBeInTheDocument();
    });

    // Verify main body text
    expect(
      screen.getByText(
        /Your XLSForm was imported successfully, but Kobo and Akvo MIS don't work identically/i
      )
    ).toBeInTheDocument();

    // Verify checklist title
    expect(screen.getByText("Common things to check:")).toBeInTheDocument();

    // Verify each checklist item
    expect(
      screen.getByText(
        /Calculated fields – formulas may need to be re-verified/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Dynamic repeat counts – repeat groups driven by a variable may need manual setup/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Group relevance \/ skip logic – conditional group visibility should be double-checked/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /"Other" follow-up questions – these aren't auto-converted; add them manually if needed/i
      )
    ).toBeInTheDocument();

    // Verify recommendation callout
    expect(
      screen.getByText(
        /We recommend previewing the full form and testing a submission before it goes live\./i
      )
    ).toBeInTheDocument();
  });
});
