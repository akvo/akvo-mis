import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { DataOnboardingCreate, DataOnboardingDetail } from "..";
import { api, uiText } from "../../../lib";

jest.mock("../../../lib/api", () => ({
  get: jest.fn(),
  post: jest.fn(),
  token: "mock-token",
}));

const text = uiText.en;

const proposal = {
  administration: {
    levels: ["Country", "District"],
    source: { sheet: "csv", columns: ["district"] },
    units: [["North"], ["North", "Hilltop"]],
    aliases: [],
  },
  forms: [
    {
      key: "sites",
      name: "Water sites",
      type: "registration",
      parent: null,
      question_group: [
        {
          name: "site",
          label: "Site",
          question: [
            {
              name: "water_source",
              label: "Water source",
              type: "option",
              required: false,
              meta: false,
              option: [{ label: "Borehole", value: "borehole" }],
              rule: null,
              extra: null,
            },
          ],
        },
      ],
    },
  ],
  data: [
    {
      form: "sites",
      sheet: "csv",
      key_columns: ["site_id"],
      administration_columns: ["district"],
      geo: null,
      columns: [{ question: "water_source", column: "source_col" }],
      value_maps: [
        {
          question: "water_source",
          values: [{ raw: "BH", label: "Borehole" }],
        },
      ],
      date_format: null,
      multi_separator: null,
      unmapped_columns: [{ column: "phone", reason: "Personal data" }],
    },
  ],
  notes: ["site_id identifies each site."],
};

const renderAt = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/control-center/data-onboarding/create"
          element={<DataOnboardingCreate />}
        />
        <Route
          path="/control-center/data-onboarding/:id"
          element={<DataOnboardingDetail />}
        />
      </Routes>
    </MemoryRouter>
  );

describe("Data Onboarding", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows why an upload was refused", async () => {
    api.post.mockRejectedValue({
      response: { data: { message: "Upload a CSV or xlsx file." } },
    });
    const { container } = renderAt("/control-center/data-onboarding/create");
    const input = container.querySelector("input[type=file]");
    fireEvent.change(input, {
      target: { files: [new File(["{}"], "data.json")] },
    });
    expect(
      await screen.findByText("Upload a CSV or xlsx file.")
    ).toBeInTheDocument();
  });

  it("shows progress, then the Proposal read-only", async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: 7, status: "drafting" } })
      .mockResolvedValue({
        data: { id: 7, status: "proposed", file_name: "s.csv", proposal },
      });
    jest.useFakeTimers();
    renderAt("/control-center/data-onboarding/7");
    expect(await screen.findByText(text.dataOnboardingDrafting)).toBeVisible();
    jest.advanceTimersByTime(3000);
    jest.useRealTimers();

    expect(await screen.findByText("Water sites")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/data-onboarding/7");
    expect(screen.getByText("Hilltop")).toBeInTheDocument();
    expect(screen.getAllByText("Water source").length).toBeGreaterThan(0);
    expect(screen.getByText("source_col")).toBeInTheDocument();
    expect(screen.getByText("BH")).toBeInTheDocument();
    expect(screen.getByText("Personal data")).toBeInTheDocument();
    expect(
      screen.getByText("site_id identifies each site.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /apply/i })).toBeNull();
  });

  it("shows a failed draft", async () => {
    api.get.mockResolvedValue({
      data: { id: 8, status: "failed", error: "OpenAI did not return JSON." },
    });
    renderAt("/control-center/data-onboarding/8");
    expect(
      await screen.findByText("OpenAI did not return JSON.")
    ).toBeInTheDocument();
  });
});
