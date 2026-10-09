import React from "react";
import { render, waitFor } from "@testing-library/react";
import axios from "axios";
import useVisualizationRequest, {
  __clearVisualizationCache,
} from "../hooks/useVisualizationRequest";

jest.mock("axios");

// VIZ-027 D-15: global_criteria is an array, one value per entry. Axios
// 0.25 would send it as `global_criteria[]=…`, which Django's
// getlist("global_criteria") does not read. The request hook therefore
// serializes params itself: arrays repeat the key, nothing else changes.

const Probe = ({ params }) => {
  useVisualizationRequest("visualization/values", params);
  return null;
};

const serializedFor = async (params) => {
  render(<Probe params={params} />);
  await waitFor(() => expect(axios).toHaveBeenCalled());
  const config = axios.mock.calls[0][0];
  expect(typeof config.paramsSerializer).toBe("function");
  return config.paramsSerializer(config.params);
};

beforeEach(() => {
  axios.mockReset();
  axios.mockResolvedValue({ data: [] });
  __clearVisualizationCache();
});

test("an array repeats the key, without brackets", async () => {
  const query = await serializedFor({
    form_id: 7002,
    global_criteria: [
      "option_in:7003:infrastructure_status:non_operational",
      "option_in:7003:infrastructure_status:operational",
    ],
  });
  expect(query).not.toContain("%5B%5D");
  expect(new URLSearchParams(query).getAll("global_criteria")).toEqual([
    "option_in:7003:infrastructure_status:non_operational",
    "option_in:7003:infrastructure_status:operational",
  ]);
});

test("a value with `:`, `,` and `|` survives the round trip", async () => {
  const query = await serializedFor({
    global_criteria: [
      "option_in:7003:infrastructure_status:pump:_broken,_leaking|pipe",
    ],
  });
  expect(new URLSearchParams(query).getAll("global_criteria")).toEqual([
    "option_in:7003:infrastructure_status:pump:_broken,_leaking|pipe",
  ]);
});

test("scalars are sent as before, and null is skipped", async () => {
  const query = await serializedFor({
    form_id: 7002,
    group_by: "option",
    administration_id: null,
  });
  expect(query).toBe("form_id=7002&group_by=option");
});
