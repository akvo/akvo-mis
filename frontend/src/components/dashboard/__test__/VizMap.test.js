import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import VizMap from "../widgets/VizMap";

// Leaflet does not run under jsdom, and the assertion here is about the
// props we hand MapCluster, not about tiles painting. Same stand-in
// approach as ChartRenderer.test.js.
let lastProps = null;
// Mounts, not renders. A Leaflet cluster group is built in an effect and
// captures its icon function there, so "did this remount?" is the only
// honest way to ask whether a prop change reached the map at all — DOM
// identity does not answer it reliably under rerender.
let mountCount = 0;
jest.mock("akvo-charts", () => {
  const RealReact = require("react");
  return {
    MapCluster: (props) => {
      lastProps = props;
      RealReact.useEffect(() => {
        mountCount += 1;
      }, []);
      return <div data-testid="map-cluster" />;
    },
  };
});

const widget = (config = {}) => ({
  id: 1,
  type: "map",
  title: "Sites",
  color: null,
  form: 6002,
  question: 600203,
  config: { chart_colors: ["#64A73B"], ...config },
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
  mountCount = 0;
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

  test("scheme colours produce a legend when palette has multiple colours", () => {
    const multiColor = widget({
      chart_colors: ["#1890ff", "#64A73B", "#F5A623"],
    });
    render(<VizMap config={multiColor} data={POINTS} />);
    expect(screen.getByText("operational")).toBeInTheDocument();
    expect(screen.getByText("issue")).toBeInTheDocument();
  });

  test("no legend when all pins share one colour", () => {
    render(<VizMap config={widget()} data={POINTS} />);
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

describe("tiles are readable by a canvas", () => {
  test("the tile layer is requested in CORS mode", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    // Without this, every tile taints the export canvas and the PNG or
    // PDF comes back with the basemap missing (VIZ-023 D-4). The tile
    // host sends access-control-allow-origin: *, so asking for CORS
    // mode costs nothing and is what makes the pixels readable.
    expect(lastProps.tile.crossOrigin).toBe("anonymous");
  });
});

// A map bound to a number question (#382). The question dropdown has
// always offered number questions; before this, picking one produced an
// empty `status_colors`, no status request, and a map of identical dots
// that ignored the question entirely.
describe("quantity mode", () => {
  const quantityWidget = (config = {}) =>
    widget({ map_mode: "quantity", ...config });

  const VALUED = [
    { id: 1, name: "Nadi Central EPS", geo: [-17.78, 177.94], value: 12000 },
    { id: 2, name: "Ba Riverside EPS", geo: [-17.53, 177.67], value: 3400 },
  ];

  test("the cluster switches to the quantity type", () => {
    render(<VizMap config={quantityWidget()} data={VALUED} />);
    expect(lastProps.type).toBe("quantity");
    expect(lastProps.valueKey).toBe("value");
  });

  test("category mode is untouched by the new branch", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    expect(lastProps.type).toBe("circle");
    expect(lastProps.groupKey).toBe("status");
  });

  test("the joined number reaches the point as a number", () => {
    render(<VizMap config={quantityWidget()} data={VALUED} />);
    expect(lastProps.data.map((d) => d.value)).toEqual([12000, 3400]);
  });

  test("a point the join missed carries null, never a made-up zero", () => {
    // MapCluster reads `Number(d[valueKey]) || 0`, so null still draws
    // the small circle that honestly says "no number here" — without
    // this component asserting a zero the data never contained. NaN
    // would size the circle as garbage; null does not.
    render(
      <VizMap
        config={quantityWidget()}
        data={[...VALUED, { id: 3, name: "Lautoka", geo: [-17.6, 177.4] }]}
      />
    );
    expect(lastProps.data[2].value).toBeNull();
    expect(Number(lastProps.data[2].value) || 0).toBe(0);
  });

  test("a non-numeric answer is null, not NaN and not zero", () => {
    render(
      <VizMap
        config={quantityWidget()}
        data={[{ id: 1, name: "Nadi", geo: [-17.7, 177.9], value: "n/a" }]}
      />
    );
    expect(lastProps.data[0].value).toBeNull();
  });

  test("a real zero survives as a zero", () => {
    // The distinction only means something if an actual 0 still reads
    // as 0 rather than being folded in with the unanswered.
    render(
      <VizMap
        config={quantityWidget()}
        data={[{ id: 1, name: "Nadi", geo: [-17.7, 177.9], value: 0 }]}
      />
    );
    expect(lastProps.data[0].value).toBe(0);
  });

  test("renderPopup is dropped so the library shows label and value", () => {
    // MapCluster only renders its own label + exact value popup when
    // renderPopup is absent; a function here overrides it and the number
    // becomes unreadable — the circle shows a compact "12K" and nothing
    // else tells you it is 12,000.
    render(<VizMap config={quantityWidget()} data={VALUED} />);
    expect(lastProps.renderPopup).toBeNull();
  });

  test("category mode keeps its label popup", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    expect(typeof lastProps.renderPopup).toBe("function");
    // The popup is handed a mapped point, whose `name` has already
    // become `label` — not the raw row.
    expect(lastProps.renderPopup(lastProps.data[0])).toBe("Nadi Central EPS");
  });

  test("circles take one colour rather than a status palette", () => {
    render(
      <VizMap
        config={quantityWidget({ chart_colors: ["#64A73B"] })}
        data={VALUED}
      />
    );
    expect(lastProps.color).toBe("#64A73B");
  });

  test("the status legend is hidden — size carries the meaning", () => {
    // A colour legend beside uniformly coloured circles describes
    // nothing that is on screen.
    render(
      <VizMap
        config={quantityWidget({ status_colors: STATUS_COLORS })}
        data={[
          { ...VALUED[0], status: "issue" },
          { ...VALUED[1], status: "operational" },
        ]}
      />
    );
    expect(document.querySelector(".dashboard-view-map-legend")).toBeNull();
  });

  test("switching mode remounts the cluster rather than reusing it", () => {
    // `key` is not observable through props, but its effect is: Leaflet
    // objects are created in an effect and do not follow React prop
    // updates, so a reused instance would keep drawing the old icons.
    const { rerender } = render(<VizMap config={widget()} data={POINTS} />);
    expect(mountCount).toBe(1);
    rerender(<VizMap config={quantityWidget()} data={VALUED} />);
    expect(mountCount).toBe(2);
  });
});

// A map bound to a value question, with clustering OFF (#387). This is
// the default for a value question: the author sees individual sites
// coloured by band, and opts into clustering when they want totals.
describe("range mode", () => {
  const RANGES = [
    { to: 340, color: "#d73027" },
    { to: 890, color: "#fee08b" },
    { to: null, color: "#1a9850" },
  ];

  const rangeWidget = (config = {}) =>
    widget({ map_mode: "range", value_ranges: RANGES, ...config });

  const VALUED = [
    { id: 1, name: "Nadi Central EPS", geo: [-17.78, 177.94], value: 120 },
    { id: 2, name: "Ba Riverside EPS", geo: [-17.53, 177.67], value: 500 },
    { id: 3, name: "Lautoka EPS", geo: [-17.6, 177.4], value: 12000 },
  ];

  test("points are not clustered", () => {
    render(<VizMap config={rangeWidget()} data={VALUED} />);
    expect(lastProps.cluster).toBe(false);
  });

  test("category and quantity maps stay clustered", () => {
    render(<VizMap config={widget()} data={POINTS} />);
    expect(lastProps.cluster).not.toBe(false);
    render(<VizMap config={widget({ map_mode: "quantity" })} data={POINTS} />);
    expect(lastProps.cluster).not.toBe(false);
  });

  test("each point takes the colour of its band", () => {
    render(<VizMap config={rangeWidget()} data={VALUED} />);
    expect(lastProps.data.map((d) => d.color)).toEqual([
      "#d73027",
      "#fee08b",
      "#1a9850",
    ]);
  });

  test("a point with no answer falls back rather than reading as zero", () => {
    // "not reported" and "nobody" are different facts; colouring the
    // first as the lowest band asserts something the data never said.
    render(
      <VizMap
        config={rangeWidget()}
        data={[{ id: 9, name: "Unknown", geo: [-17.7, 177.9] }]}
      />
    );
    expect(lastProps.data[0].color).toBe("#64A73B");
  });

  test("the legend names the bands, not the statuses", () => {
    render(<VizMap config={rangeWidget()} data={VALUED} />);
    expect(screen.getByText("under 340")).toBeInTheDocument();
    expect(screen.getByText("340 – 890")).toBeInTheDocument();
    expect(screen.getByText("890 and above")).toBeInTheDocument();
  });

  test("the popup carries the number, not just the name", () => {
    // A coloured dot says which band; without this nothing on screen
    // ever says which value.
    render(<VizMap config={rangeWidget()} data={VALUED} />);
    const { container } = require("@testing-library/react").render(
      <div>{lastProps.renderPopup(lastProps.data[2])}</div>
    );
    expect(container.textContent).toContain("Lautoka EPS");
    expect(container.textContent).toContain("12,000");
  });

  test("an unanswered point says so, rather than claiming zero", () => {
    // The colour already falls back for a missing answer; a popup
    // reading "0" would tell the reader this site serves nobody, which
    // is a different fact from nobody having reported.
    render(
      <VizMap
        config={rangeWidget()}
        data={[{ id: 9, name: "Unknown", geo: [-17.7, 177.9] }]}
      />
    );
    const { container } = require("@testing-library/react").render(
      <div>{lastProps.renderPopup(lastProps.data[0])}</div>
    );
    expect(container.textContent).toContain("Unknown");
    expect(container.textContent).toContain("No value");
    expect(container.textContent).not.toContain("0");
  });

  test("a site that really reported zero still shows zero", () => {
    render(
      <VizMap
        config={rangeWidget()}
        data={[{ id: 9, name: "Empty", geo: [-17.7, 177.9], value: 0 }]}
      />
    );
    const { container } = require("@testing-library/react").render(
      <div>{lastProps.renderPopup(lastProps.data[0])}</div>
    );
    expect(container.textContent).toContain("0");
    expect(container.textContent).not.toContain("No value");
  });

  test("no bands configured yet still renders the map", () => {
    // The seeding request can fail; the author gets an uncoloured map
    // rather than a broken widget.
    render(<VizMap config={rangeWidget({ value_ranges: [] })} data={VALUED} />);
    expect(screen.getByTestId("map-cluster")).toBeInTheDocument();
    expect(lastProps.data.every((d) => d.color === "#64A73B")).toBe(true);
    expect(document.querySelector(".dashboard-view-map-legend")).toBeNull();
  });
});

describe("quantity aggregation", () => {
  const VALUED = [
    { id: 1, name: "Nadi", geo: [-17.78, 177.94], value: 120 },
    { id: 2, name: "Ba", geo: [-17.53, 177.67], value: 500 },
  ];

  test("sum is the default a cluster combines by", () => {
    render(<VizMap config={widget({ map_mode: "quantity" })} data={VALUED} />);
    expect(lastProps.aggregate).toBe("sum");
  });

  test("the author's choice reaches the library", () => {
    // Sum is wrong for a rate: five sites at 50 l/p/d is not 250.
    render(
      <VizMap
        config={widget({ map_mode: "quantity", map_aggregate: "average" })}
        data={VALUED}
      />
    );
    expect(lastProps.aggregate).toBe("average");
  });

  test("changing how a cluster combines remounts it", () => {
    // MapCluster keys its Leaflet group on `type` and `cluster` only, and
    // MarkerClusterGroup captures iconCreateFunction at mount by design
    // ("a caller that needs a different closure is expected to remount
    // this component"). Without the aggregate in OUR key, switching
    // Sum -> Average leaves the old closure in place and every circle
    // carries on summing, with nothing on screen to say so.
    const { rerender } = render(
      <VizMap
        config={widget({ map_mode: "quantity", map_aggregate: "sum" })}
        data={VALUED}
      />
    );
    expect(mountCount).toBe(1);
    rerender(
      <VizMap
        config={widget({ map_mode: "quantity", map_aggregate: "average" })}
        data={VALUED}
      />
    );
    expect(lastProps.aggregate).toBe("average");
    expect(mountCount).toBe(2);
  });

  test("a cluster label is rounded, not a repeating decimal", () => {
    // Sums are whole, so the library's default never had to round; an
    // average divides, and 11/3 rendered as 3.6666666666 inside a 40px
    // circle.
    render(<VizMap config={widget({ map_mode: "quantity" })} data={VALUED} />);
    expect(lastProps.formatValue(11 / 3)).toBe("3.67");
    expect(lastProps.formatValue(2.5)).toBe("2.5");
    expect(lastProps.formatValue(7)).toBe("7");
  });

  test("large numbers keep their compact form", () => {
    // Rounding must not cost the K/M/B shorthand the circle relies on to
    // fit a real population figure.
    render(<VizMap config={widget({ map_mode: "quantity" })} data={VALUED} />);
    expect(lastProps.formatValue(12400)).toBe("12.4K");
    expect(lastProps.formatValue(10562088)).toBe("10.6M");
    expect(lastProps.formatValue(2.4e9)).toBe("2.4B");
  });

  test("range mode passes no aggregate at all", () => {
    render(
      <VizMap
        config={widget({ map_mode: "range", value_ranges: [] })}
        data={VALUED}
      />
    );
    expect(lastProps.aggregate).toBeUndefined();
  });
});
