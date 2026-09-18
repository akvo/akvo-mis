import React from "react";
import { render } from "@testing-library/react";
import GeometryView from "../GeometryView";

/**
 * Leaflet needs a sized container and a real layout pass, neither of which jsdom
 * provides. The map itself is exercised in the browser; what is worth asserting here
 * is the data handling around it — what gets passed in, and what is summarised.
 */
jest.mock("react-leaflet", () => ({
  MapContainer: ({ children, ...props }) => (
    <div data-testid="map" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Polygon: ({ positions }) => (
    <div data-testid="polygon" data-positions={JSON.stringify(positions)} />
  ),
  Polyline: ({ positions }) => (
    <div data-testid="polyline" data-positions={JSON.stringify(positions)} />
  ),
  CircleMarker: ({ center }) => (
    <div data-testid="vertex" data-center={JSON.stringify(center)} />
  ),
}));

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

describe("GeometryView", () => {
  test("shows a dash when there is no shape", () => {
    const { container, queryByTestId } = render(<GeometryView value={null} />);
    expect(container.textContent).toBe("-");
    expect(queryByTestId("map")).toBeNull();
  });

  test("shows a dash for an unparseable answer", () => {
    const { container } = render(<GeometryView value="[not json" />);
    expect(container.textContent).toBe("-");
  });

  test("draws the polygon and one marker per vertex", () => {
    const { getByTestId, getAllByTestId } = render(
      <GeometryView value={triangle} />
    );
    expect(JSON.parse(getByTestId("polygon").dataset.positions)).toEqual(
      triangle
    );
    expect(getAllByTestId("vertex")).toHaveLength(3);
  });

  test("accepts a JSON string answer", () => {
    const { getByTestId } = render(
      <GeometryView value={JSON.stringify(triangle)} />
    );
    expect(JSON.parse(getByTestId("polygon").dataset.positions)).toEqual(
      triangle
    );
  });

  test("fits the map to the shape", () => {
    const { getByTestId } = render(<GeometryView value={triangle} />);
    expect(JSON.parse(getByTestId("map").dataset.props).bounds).toEqual(
      triangle
    );
  });

  /**
   * A preview of a saved answer, not a viewer: every interaction handler is off. Wheel
   * zoom would otherwise swallow the page scroll, and panning would let a reviewer lose
   * the shape off-screen with no control to bring it back.
   */
  test("is completely static - no dragging, zooming or keyboard", () => {
    const { getByTestId } = render(<GeometryView value={triangle} />);
    const props = JSON.parse(getByTestId("map").dataset.props);
    expect(props.dragging).toBe(false);
    expect(props.scrollWheelZoom).toBe(false);
    expect(props.doubleClickZoom).toBe(false);
    expect(props.touchZoom).toBe(false);
    expect(props.boxZoom).toBe(false);
    expect(props.keyboard).toBe(false);
    expect(props.zoomControl).toBe(false);
  });

  test("summarises point count and area", () => {
    const { container } = render(<GeometryView value={triangle} />);
    expect(container.textContent).toContain("Points: 3");
    expect(container.textContent).toMatch(/Area: [\d.]+ ha/);
  });

  /*
    Asserted on "Area:" rather than on the bare substring "ha": the validation badge added by
    GEO-002 D-7 can legitimately render words containing those two letters ("shape"), and a
    test that passes only because no other text happens to contain a common digraph is a trap
    for the next person, not a check on this component.
  */
  test("withholds the area below three points", () => {
    const { container } = render(<GeometryView value={triangle.slice(0, 2)} />);
    expect(container.textContent).toContain("Points: 2");
    expect(container.textContent).not.toContain("Area:");
  });

  test("badges a self-intersecting shape without claiming it was blocked", () => {
    const bowtie = [
      [0, 0],
      [0.01, 0.01],
      [0.01, 0],
      [0, 0.01],
    ];
    const { getByTestId, container } = render(<GeometryView value={bowtie} />);
    expect(getByTestId("geometry-warning-selfIntersection")).toHaveTextContent(
      "Boundary crosses itself"
    );
    // Severity was settled on the device at capture; the web must not imply it knows.
    expect(container.textContent).not.toMatch(
      /blocked|rejected|invalid submission/i
    );
  });

  test("shows no badge for geometry that passes", () => {
    const { queryByTestId } = render(<GeometryView value={triangle} />);
    expect(queryByTestId("geometry-warning-selfIntersection")).toBeNull();
    expect(queryByTestId("geometry-warning-minArea")).toBeNull();
  });

  /**
   * geoshape is a closed ring with an enclosed area; geotrace is an open line, so it
   * draws as a Polyline and reports no area. Backend siblings: QuestionTypes.geoshape
   * = 14, geotrace = 15.
   */
  test("draws a geotrace as an open line with no area", () => {
    const { container, getByTestId, queryByTestId } = render(
      <GeometryView value={triangle} type="geotrace" />
    );
    expect(JSON.parse(getByTestId("polyline").dataset.positions)).toEqual(
      triangle
    );
    expect(queryByTestId("polygon")).toBeNull();
    expect(container.textContent).toContain("Points: 3");
    expect(container.textContent).not.toContain("ha");
  });

  test("defaults to a closed shape when no type is given", () => {
    const { getByTestId, queryByTestId } = render(
      <GeometryView value={triangle} />
    );
    expect(getByTestId("polygon")).toBeDefined();
    expect(queryByTestId("polyline")).toBeNull();
  });

  /**
   * The coordinates must reach Leaflet as [lat, lng] — akvo-react-form's order. A swap
   * renders a plausible polygon on the wrong continent (GEO-001 D-1b).
   */
  test("passes latitude first to the map", () => {
    const { getAllByTestId } = render(<GeometryView value={triangle} />);
    const [lat, lng] = JSON.parse(getAllByTestId("vertex")[0].dataset.center);
    expect(lat).toBe(9.03);
    expect(lng).toBe(38.74);
  });
});
