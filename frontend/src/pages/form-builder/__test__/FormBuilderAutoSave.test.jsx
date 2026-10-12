import React from "react";
import { render, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import FormBuilderEdit from "../FormBuilderEdit";
import FormBuilderCreate from "../FormBuilderCreate";
import { api, store } from "../../../lib";

let lastEditorProps = {};

jest.mock("akvo-react-form-editor", () => {
  const MockWebformEditor = (props) => {
    lastEditorProps = props;
    return <div data-testid="mock-webform-editor">Mock Editor</div>;
  };
  MockWebformEditor.displayName = "MockWebformEditor";
  return MockWebformEditor;
});

jest.mock("../../../components/can", () => {
  const MockCan = ({ children }) => <>{children}</>;
  MockCan.displayName = "MockCan";
  return {
    Can: MockCan,
    AbilityContext: {
      Provider: ({ children }) => <>{children}</>,
    },
  };
});

jest.mock("../../../lib/api", () => ({
  get: jest.fn(),
  put: jest.fn(),
  post: jest.fn(),
  token: "mock-token",
}));

jest.mock("../../../util/hooks", () => ({
  useNotification: () => ({ notify: jest.fn() }),
}));

jest.mock("../../../util/form", () => ({
  fetchPublishedForms: jest.fn(),
}));

describe("FormBuilder Auto-Save & Draft Recovery Props", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    lastEditorProps = {};
    store.update((s) => {
      s.language = { active: "en" };
      s.user = { administration: { id: 1 } };
    });
  });

  test("FormBuilderCreate passes enableAutoSave and enableDraftRecovery props", async () => {
    render(
      <MemoryRouter initialEntries={["/control-center/form-builder/create"]}>
        <Routes>
          <Route
            path="/control-center/form-builder/create"
            element={<FormBuilderCreate />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(lastEditorProps.enableAutoSave).toBe(true);
    expect(lastEditorProps.enableDraftRecovery).toBe(true);
  });

  test("FormBuilderEdit passes auto-save configuration and triggers onAutoSave API call", async () => {
    api.get.mockResolvedValue({
      data: {
        id: 42,
        name: "Test Form",
        status: "draft",
        version: 1.0,
        latest_version: 1.0,
        question_group: [],
      },
    });

    api.put.mockResolvedValue({
      data: {
        id: 42,
        name: "Test Form",
        status: "draft",
        version: 1.1,
        latest_version: 1.1,
      },
    });

    render(
      <MemoryRouter initialEntries={["/control-center/form-builder/42/edit"]}>
        <Routes>
          <Route
            path="/control-center/form-builder/:formId/edit"
            element={<FormBuilderEdit />}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/manage/forms/42");
    });

    expect(lastEditorProps.enableAutoSave).toBe(true);
    expect(lastEditorProps.autoSaveInterval).toBe(30000);
    expect(lastEditorProps.enableDraftRecovery).toBe(true);
    expect(typeof lastEditorProps.onAutoSave).toBe("function");

    // Simulate auto-save callback execution
    const mockOutput = { name: "Updated Form Name", question_group: [] };
    await act(async () => {
      await lastEditorProps.onAutoSave(mockOutput);
    });

    expect(api.put).toHaveBeenCalledWith(
      "/manage/forms/42?allow_delete=true",
      mockOutput
    );
  });
});
