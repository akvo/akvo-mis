import dashboardApi from "../dashboardApi";
import api from "../../lib/api";
import { store } from "../../lib";

jest.mock("../../lib/api");

const version = () => store.currentState.dashboardsVersion;

describe("dashboardApi list invalidation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.get.mockResolvedValue({ data: [] });
    api.post.mockResolvedValue({ data: {} });
    api.put.mockResolvedValue({ data: {} });
    api.delete.mockResolvedValue({ data: {} });
  });

  // The header menu cannot see the builder or the list page, so a write
  // has to say so here or the menu keeps showing yesterday's answer.
  it.each([
    ["create", () => dashboardApi.create({})],
    ["update", () => dashboardApi.update(1, {})],
    ["destroy", () => dashboardApi.destroy(1)],
    ["publish", () => dashboardApi.publish(1)],
    ["unpublish", () => dashboardApi.unpublish(1)],
    ["duplicate", () => dashboardApi.duplicate(1)],
    ["setVisibility", () => dashboardApi.setVisibility(1, true)],
  ])("%s marks the published list stale", async (_name, call) => {
    const before = version();
    await call();
    expect(version()).toBe(before + 1);
  });

  it.each([
    ["list", () => dashboardApi.list()],
    ["get", () => dashboardApi.get(1)],
    ["listPublished", () => dashboardApi.listPublished()],
    ["getPublished", () => dashboardApi.getPublished("slug")],
  ])("%s changes nothing", async (_name, call) => {
    const before = version();
    await call();
    expect(version()).toBe(before);
  });

  it("does not invalidate when the write fails", async () => {
    api.post.mockRejectedValue(new Error("nope"));
    const before = version();
    await expect(dashboardApi.publish(1)).rejects.toThrow();
    expect(version()).toBe(before);
  });
});
