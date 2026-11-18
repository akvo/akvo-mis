import React from "react";
import { act, render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import {
  DataOnboardingCreate,
  DataOnboardingDetail,
  DataOnboardingList,
} from "..";
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
          path="/control-center/data-onboarding"
          element={<DataOnboardingList />}
        />
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
        data: {
          id: 7,
          status: "proposed",
          file_name: "s.csv",
          proposal,
          units: { new: [["North"], ["North", "Hilltop"]], outside: [] },
        },
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
  });

  it("applies the Proposal, then shows the Onboarding Report", async () => {
    api.get
      .mockResolvedValueOnce({
        data: { id: 7, status: "proposed", file_name: "s.csv", proposal },
      })
      .mockResolvedValue({
        data: {
          id: 7,
          status: "applied",
          file_name: "s.csv",
          proposal,
          report: {
            forms: [{ key: "sites", name: "Water sites", form: 3, loaded: 41 }],
            issues: [
              {
                sheet: "csv",
                row: 5,
                question: "water_source",
                kind: "warning",
                reason: "Not one of the options.",
              },
            ],
          },
        },
      });
    api.post.mockResolvedValue({
      data: { id: 7, status: "applying", file_name: "s.csv", proposal },
    });
    renderAt("/control-center/data-onboarding/7");
    const apply = await screen.findByRole("button", {
      name: text.dataOnboardingApply,
    });
    jest.useFakeTimers();
    fireEvent.click(apply);
    expect(api.post).toHaveBeenCalledWith("/data-onboarding/7/apply");
    expect(
      await screen.findByText(text.dataOnboardingApplying)
    ).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(
      await screen.findByText(text.dataOnboardingReport)
    ).toBeInTheDocument();
    jest.useRealTimers();
    expect(screen.getByText("41")).toBeInTheDocument();
    expect(screen.getByText("Not one of the options.")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: text.dataOnboardingApply })
    ).toBeNull();
  });

  const blocked = [
    {
      form: "sites",
      name: "Water sites",
      causes: [
        {
          kind: "near_match",
          reason: "Some new units are spelled like existing units.",
          units: [{ name: "Kwalle", match: "Kwale" }],
        },
        {
          kind: "shared_name",
          reason: "Some names exist under several parents.",
          units: [
            {
              name: "Hill",
              parents: [
                { id: 2, name: "North" },
                { id: 3, name: "South" },
              ],
            },
          ],
        },
      ],
    },
  ];

  it("drops and keeps columns, and sends a revision", async () => {
    const proposed = { id: 7, status: "proposed", proposal };
    api.get.mockResolvedValue({ data: proposed });
    api.post.mockResolvedValue({ data: proposed });
    renderAt("/control-center/data-onboarding/7");
    await screen.findByText("Water sites");

    fireEvent.click(
      screen.getByRole("button", { name: text.dataOnboardingDropColumn })
    );
    expect(api.post).toHaveBeenCalledWith("/data-onboarding/7/edits", {
      op: "drop_column",
      form: "sites",
      column: "source_col",
    });
    fireEvent.click(
      screen.getByRole("button", { name: text.dataOnboardingKeepColumn })
    );
    expect(api.post).toHaveBeenCalledWith("/data-onboarding/7/edits", {
      op: "keep_column",
      form: "sites",
      column: "phone",
    });

    fireEvent.change(
      screen.getByPlaceholderText(text.dataOnboardingReviseHint),
      { target: { value: "Make it a yes/no question" } }
    );
    fireEvent.click(
      screen.getByRole("button", { name: text.dataOnboardingRevise })
    );
    expect(api.post).toHaveBeenCalledWith("/data-onboarding/7/revise", {
      instruction: "Make it a yes/no question",
    });
  });

  it("shows a failed revision with the Proposal kept", async () => {
    api.get.mockResolvedValue({
      data: { id: 7, status: "proposed", proposal, error: "No Proposal." },
    });
    renderAt("/control-center/data-onboarding/7");
    expect(
      await screen.findByText(text.dataOnboardingRevisionFailed)
    ).toBeInTheDocument();
    expect(screen.getByText("No Proposal.")).toBeInTheDocument();
    expect(screen.getByText("Water sites")).toBeInTheDocument();
  });

  it("resolves a near-match in the review, then can apply", async () => {
    api.get.mockResolvedValue({
      data: { id: 7, status: "proposed", proposal, blocked },
    });
    api.post.mockResolvedValue({
      data: { id: 7, status: "proposed", proposal, blocked: [] },
    });
    renderAt("/control-center/data-onboarding/7");
    fireEvent.click(
      await screen.findByRole("button", {
        name: text.dataOnboardingUseExisting,
      })
    );
    expect(api.post).toHaveBeenCalledWith("/data-onboarding/7/edits", {
      op: "resolve_near_match",
      name: "Kwalle",
      match: "Kwale",
      use: "existing",
    });
    expect(
      await screen.findByRole("button", { name: text.dataOnboardingApply })
    ).toBeEnabled();
    expect(screen.queryByText(text.dataOnboardingBlocked)).toBeNull();
  });

  it("drops a form that has no location column", async () => {
    const noLocation = [
      {
        form: "sites",
        name: "Water sites",
        causes: [{ kind: "no_location", reason: "No location column." }],
      },
    ];
    api.get.mockResolvedValue({
      data: { id: 7, status: "proposed", proposal, blocked: noLocation },
    });
    api.post.mockResolvedValue({
      data: { id: 7, status: "proposed", proposal, blocked: noLocation },
    });
    renderAt("/control-center/data-onboarding/7");
    fireEvent.click(
      await screen.findByRole("button", { name: text.dataOnboardingDropForm })
    );
    expect(api.post).toHaveBeenCalledWith("/data-onboarding/7/edits", {
      op: "drop_form",
      form: "sites",
    });
  });

  it("marks a blocked form with its causes and won't apply it", async () => {
    api.get.mockResolvedValue({
      data: { id: 7, status: "proposed", proposal, blocked },
    });
    renderAt("/control-center/data-onboarding/7");
    expect(
      await screen.findByText("Some new units are spelled like existing units.")
    ).toBeInTheDocument();
    expect(screen.getByText(text.dataOnboardingBlocked)).toBeInTheDocument();
    expect(screen.getByText(/Kwalle → Kwale/)).toBeInTheDocument();
    expect(screen.getByText("Hill")).toBeInTheDocument();
    expect(screen.getByText(text.dataOnboardingBlockedNote)).toBeVisible();
    expect(
      screen.getByRole("button", { name: text.dataOnboardingApply })
    ).toBeDisabled();
  });

  it("lists the forms the re-check at Apply blocked", async () => {
    api.get.mockResolvedValue({
      data: {
        id: 7,
        status: "applied",
        proposal,
        report: { forms: [], issues: [], blocked },
      },
    });
    renderAt("/control-center/data-onboarding/7");
    expect(
      await screen.findByText(text.dataOnboardingNotApplied)
    ).toBeInTheDocument();
    expect(screen.getByText("Water sites")).toBeInTheDocument();
    expect(
      screen.getByText("Some names exist under several parents.")
    ).toBeInTheDocument();
  });

  it("shows the units Apply adds from the file, and those left out", async () => {
    api.get.mockResolvedValue({
      data: {
        id: 7,
        status: "proposed",
        file_name: "s.csv",
        proposal,
        units: {
          new: [
            ["North", "Hill"],
            ["North", "Vale"],
          ],
          outside: [["South"], ["South", "Dale"]],
        },
      },
    });
    renderAt("/control-center/data-onboarding/7");
    expect(await screen.findByText("Vale")).toBeInTheDocument();
    expect(screen.getByText(text.dataOnboardingUnitsOutside)).toBeVisible();
    expect(screen.getByText("South, South › Dale")).toBeInTheDocument();
  });

  it("shows the registration form of each monitoring form", async () => {
    const visits = {
      ...proposal.forms[0],
      key: "visits",
      name: "Site visits",
      type: "monitoring",
      parent: "sites",
    };
    api.get.mockResolvedValue({
      data: {
        id: 7,
        status: "proposed",
        file_name: "s.csv",
        proposal: { ...proposal, forms: [...proposal.forms, visits] },
      },
    });
    renderAt("/control-center/data-onboarding/7");
    expect(await screen.findByText("Site visits")).toBeInTheDocument();
    expect(
      screen.getByText(`${text.dataOnboardingParentForm}: Water sites`)
    ).toBeInTheDocument();
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

  it("shows an Apply failure apart from a draft failure", async () => {
    api.get.mockResolvedValue({
      data: {
        id: 9,
        status: "failed",
        proposal,
        error: "Apply ran out of time.",
      },
    });
    renderAt("/control-center/data-onboarding/9");
    expect(
      await screen.findByText(text.dataOnboardingApplyFailed)
    ).toBeInTheDocument();
    expect(screen.queryByText(text.dataOnboardingFailed)).toBeNull();
  });

  it("lists past Data Onboardings with who ran each and when", async () => {
    api.get.mockResolvedValue({
      data: [
        {
          id: 7,
          status: "applied",
          file_name: "sites.csv",
          created: "2026-11-18T10:00:00",
          updated: "2026-11-18T10:05:00",
          created_by: "Ann Admin",
        },
      ],
    });
    renderAt("/control-center/data-onboarding");
    const link = await screen.findByRole("link", { name: "sites.csv" });
    expect(api.get).toHaveBeenCalledWith("/data-onboarding");
    expect(link).toHaveAttribute("href", "/control-center/data-onboarding/7");
    expect(screen.getByText("Ann Admin")).toBeInTheDocument();
    expect(screen.getByText("applied")).toBeInTheDocument();
    expect(screen.getByText(/2026-11-18 10:00/)).toBeInTheDocument();
  });

  it("downloads the Onboarding Report", async () => {
    api.get.mockImplementation((url) =>
      url.endsWith("/report")
        ? Promise.resolve({
            data: "xlsx",
            headers: {
              "content-disposition":
                'attachment; filename="onboarding-report-7.xlsx"',
            },
          })
        : Promise.resolve({
            data: {
              id: 7,
              status: "applied",
              proposal,
              report: { forms: [], issues: [] },
            },
          })
    );
    window.URL.createObjectURL = jest.fn(() => "blob:x");
    window.URL.revokeObjectURL = jest.fn();
    renderAt("/control-center/data-onboarding/7");
    fireEvent.click(
      await screen.findByRole("button", {
        name: new RegExp(text.dataOnboardingDownloadReport),
      })
    );
    expect(api.get).toHaveBeenCalledWith("/data-onboarding/7/report", {
      responseType: "blob",
    });
  });
});
