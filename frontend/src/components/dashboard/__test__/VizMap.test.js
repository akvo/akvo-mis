import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizMap from "../widgets/VizMap";

// Leaflet does not run under jsdom, and the assertion here is about the
// props we hand MapCluster, not about tiles painting. Same stand-in
// approach as ChartRenderer.test.js.
let lastProps = null;
jest.mock("akvo-charts", () => ({
  MapCluster: (props) => {
    lastProps = props;
    return <div data-testid="map-cluster" />;
  },
}));

const widget = (config = {}) => ({
  id: 1,
  type: "map",
  title: "Sites",
  color: "#64A73B",
  form: 6002,
  question: 600203,
  config,
});

const POINTS = [
  { id: 1, name: "Nadi Central EPS", geo: [-17.78, 177.94], status: "issue" },
  {
    id: 2,
    name: "Ba Riverside EPS",
    geo: [-17.53, 177.67],
    status: "operational",
  },
];

const STATUS_COLORS = { operational: "#64A73B", issue: "#e41a1c" };

beforeEach(() => {
  lastProps = null;
});

describe("point mapping", () => {
  test("geo becomes point unchanged", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    expect(lastProps.data.map((d) => d.point)).toEqual([
      [-17.78, 177.94],
      [-17.53, 177.67],
    ]);
  });

  test("a point without coordinates is dropped, not placed at 0,0", () => {
    render(
      <VizMap
        config={widget()}
        data={[...POINTS, { id: 3, name: "No geo", geo: null, status: null }]}
      />
    );
    expect(lastProps.data).toHaveLength(2);
  });

  test("the name travels as the popup label", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    expect(lastProps.data[0].label).toBe("Nadi Central EPS");
  });

  test("clusters group and colour by status", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    expect(lastProps.groupKey).toBe("status");
    // type="circle" draws a self-contained inline SVG donut. The default
    // cluster type would need leaflet.markercluster's stylesheet, which
    // lives in akvo-charts' nested node_modules and does not resolve from
    // application code.
    expect(lastProps.type).toBe("circle");
  });
});

describe("status colouring", () => {
  test("status_colors wins over the widget colour", () => {
    render(
      <VizMap config={widget({ status_colors: STATUS_COLORS })} data={POINTS} />
    );
    expect(lastProps.data.map((d) => d.color)).toEqual(["#e41a1c", "#64A73B"]);
  });

  test("a status with no colour assigned falls back", () => {
    render(
      <VizMap
        config={widget({ status_colors: { operational: "#64A73B" } })}
        data={POINTS}
      />
    );
    // "issue" is uncoloured here.
    expect(lastProps.data[0].color).toBe("#64A73B");
  });

  test("no status at all falls back to the widget colour", () => {
    render(
      <VizMap
        config={widget({ status_colors: STATUS_COLORS })}
        data={[{ id: 1, name: "Nadi", geo: [-17.7, 177.9], status: null }]}
      />
    );
    expect(lastProps.data[0].color).toBe("#64A73B");
  });
});

describe("legend", () => {
  test("one entry per configured status", () => {
    render(
      <VizMap config={widget({ status_colors: STATUS_COLORS })} data={POINTS} />
    );
    expect(screen.getByText("operational")).toBeInTheDocument();
    expect(screen.getByText("issue")).toBeInTheDocument();
    expect(
      document.querySelectorAll(".dashboard-view-map-legend-dot")
    ).toHaveLength(2);
  });

  test("no legend when nothing is coloured", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    // A one-entry legend for a single-colour map is noise.
    expect(document.querySelector(".dashboard-view-map-legend")).toBeNull();
  });
});

describe("empty", () => {
  test("no points still renders the map, not a blank box", () => {
    render(<VizMap config={widget()} data={[]} />);
    expect(screen.getByTestId("map-cluster")).toBeInTheDocument();
    expect(lastProps.data).toEqual([]);
  });
});
