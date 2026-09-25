import dashboardAi from "../dashboardAi";
import api from "../../lib/api";

jest.mock("../../lib/api");

describe("dashboardAi API client", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.post.mockResolvedValue({ data: {} });
  });

  it("suggestDashboard posts to /manage/dashboards/ai/suggest-dashboard with payload and signal", async () => {
    const payload = { root_form: 101, user_intent: "Analyze boreholes" };
    const controller = new AbortController();
    api.post.mockResolvedValue({
      data: {
        name: "Borehole Analysis",
        description: "AI-generated dashboard",
        widgets: [{ type: "kpi", title: "Total Boreholes" }],
      },
    });

    const res = await dashboardAi.suggestDashboard(payload, controller.signal);

    expect(api.post).toHaveBeenCalledWith(
      "manage/dashboards/ai/suggest-dashboard",
      payload,
      { signal: controller.signal }
    );
    expect(res.data.name).toBe("Borehole Analysis");
  });

  it("suggestWidgets posts to /manage/dashboards/{id}/ai/suggest-widgets with payload and signal", async () => {
    const dashboardId = 42;
    const payload = {
      existing_widget_types: ["kpi"],
      prompt_hint: "Add bar chart",
    };
    const controller = new AbortController();
    api.post.mockResolvedValue({
      data: {
        suggestions: [
          {
            type: "bar",
            title: "Breakdown by Region",
            rationale: "Shows geographical distribution",
          },
        ],
      },
    });

    const res = await dashboardAi.suggestWidgets(
      dashboardId,
      payload,
      controller.signal
    );

    expect(api.post).toHaveBeenCalledWith(
      "manage/dashboards/42/ai/suggest-widgets",
      payload,
      { signal: controller.signal }
    );
    expect(res.data.suggestions).toHaveLength(1);
    expect(res.data.suggestions[0].type).toBe("bar");
  });
});
