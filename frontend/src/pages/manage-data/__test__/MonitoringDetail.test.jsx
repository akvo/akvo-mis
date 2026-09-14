import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import MonitoringDetail from "../MonitoringDetail";
import { api, store } from "../../../lib";
import { AbilityContext } from "../../../components/can";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

const mockNotify = jest.fn();
jest.mock("../../../util/hooks", () => ({
  useNotification: () => ({ notify: mockNotify }),
}));

jest.mock("../DataDetail", () => {
  const MockDataDetail = ({ record, setDeleteData }) => (
    <div data-testid={`data-detail-${record?.id}`}>
      <span>{record?.name}</span>
      <button
        onClick={() => setDeleteData(record)}
        data-testid={`delete-btn-${record?.id}`}
      >
        Delete Data
      </button>
    </div>
  );
  MockDataDetail.displayName = "MockDataDetail";
  return MockDataDetail;
});

jest.mock("../MonitoringOverview", () => {
  const MockMonitoringOverview = () => (
    <div data-testid="monitoring-overview" />
  );
  MockMonitoringOverview.displayName = "MockMonitoringOverview";
  return MockMonitoringOverview;
});

const REGISTRATION_FORM = {
  id: 1,
  name: "Water Point Registration",
  content: {
    parent: null,
    question_group: [],
  },
};

const MONITORING_FORM = {
  id: 2,
  name: "Water Point Monitoring",
  content: {
    parent: 1,
    question_group: [],
  },
};

const DATAPOINT = {
  id: 175,
  uuid: "uuid-175",
  name: "Borehole Alpha",
  form: 1,
};

const ability = { can: () => true };

describe("MonitoringDetail deletion flow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    store.update((s) => {
      s.allForms = [REGISTRATION_FORM, MONITORING_FORM];
      s.forms = [REGISTRATION_FORM, MONITORING_FORM];
      s.selectedFormData = DATAPOINT;
      s.language = { active: "en", langs: { en: "English" } };
      s.user = { id: 1, is_superuser: true };
    });

    jest.spyOn(api, "get").mockImplementation((url) => {
      if (url.includes("/data-details/175")) {
        return Promise.resolve({ data: DATAPOINT });
      }
      if (url.includes("/form-data/2/")) {
        return Promise.resolve({
          data: {
            data: [
              { id: 201, name: "Inspection Visit 1", form: 2, uuid: "sub-1" },
              { id: 202, name: "Inspection Visit 2", form: 2, uuid: "sub-2" },
            ],
            total: 2,
          },
        });
      }
      return Promise.resolve({ data: {} });
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  const renderComponent = () =>
    render(
      <MemoryRouter initialEntries={["/control-center/data/1/monitoring/175"]}>
        <AbilityContext.Provider value={ability}>
          <Routes>
            <Route
              path="/control-center/data/:form/monitoring/:parentId"
              element={<MonitoringDetail />}
            />
          </Routes>
        </AbilityContext.Provider>
      </MemoryRouter>
    );

  test("deleting the registration datapoint redirects to /control-center/data and clears store", async () => {
    jest.spyOn(api, "delete").mockResolvedValue({ data: { success: true } });

    renderComponent();

    expect(await screen.findByTestId("delete-btn-175")).toBeInTheDocument();

    // Trigger delete modal for the registration datapoint
    fireEvent.click(screen.getByTestId("delete-btn-175"));

    // Modal should be visible with confirmation text
    expect(
      screen.getByText(/Are you sure want to delete this datapoint\?/i)
    ).toBeInTheDocument();

    // Confirm deletion inside the Modal
    const deleteButtonInModal = screen.getByRole("button", {
      name: /^Delete$/i,
    });
    fireEvent.click(deleteButtonInModal);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("data/175");
    });

    await waitFor(() => {
      expect(mockNotify).toHaveBeenCalledWith({
        type: "success",
        message: "Borehole Alpha deleted",
      });
      expect(mockNavigate).toHaveBeenCalledWith("/control-center/data");
      expect(store.getRawState().selectedFormData).toBeNull();
    });
  });

  test("deleting a monitoring child submission removes it from list and does not navigate", async () => {
    jest.spyOn(api, "delete").mockResolvedValue({ data: { success: true } });

    renderComponent();

    // Switch to Monitoring Data tab
    const monitoringTab = screen.getByRole("tab", {
      name: /Monitoring Data/i,
    });
    fireEvent.click(monitoringTab);

    // Wait for monitoring table data
    expect(await screen.findByText("Inspection Visit 1")).toBeInTheDocument();

    // Click row to expand record 201
    fireEvent.click(screen.getByText("Inspection Visit 1"));

    // Child DataDetail delete button
    expect(await screen.findByTestId("delete-btn-201")).toBeInTheDocument();

    // Trigger delete for child record 201
    fireEvent.click(screen.getByTestId("delete-btn-201"));

    // Confirm deletion inside the Modal
    const deleteButtonInModal = screen.getByRole("button", {
      name: /^Delete$/i,
    });
    fireEvent.click(deleteButtonInModal);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("data/201");
    });

    await waitFor(() => {
      expect(mockNotify).toHaveBeenCalledWith({
        type: "success",
        message: "Inspection Visit 1 deleted",
      });
      expect(mockNavigate).not.toHaveBeenCalled();
      expect(store.getRawState().selectedFormData).not.toBeNull();
    });
  });

  test("displays error notification when datapoint deletion fails and does not navigate", async () => {
    jest
      .spyOn(api, "delete")
      .mockRejectedValue(new Error("Server error deleting"));

    renderComponent();

    expect(await screen.findByTestId("delete-btn-175")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("delete-btn-175"));

    const deleteButtonInModal = screen.getByRole("button", {
      name: /^Delete$/i,
    });
    fireEvent.click(deleteButtonInModal);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("data/175");
    });

    await waitFor(() => {
      expect(mockNotify).toHaveBeenCalledWith({
        type: "error",
        message: "Could not delete datapoint",
      });
      expect(mockNavigate).not.toHaveBeenCalled();
      expect(store.getRawState().selectedFormData).not.toBeNull();
    });
  });
});
