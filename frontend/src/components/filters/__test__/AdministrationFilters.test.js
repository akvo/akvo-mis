import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AdministrationFilters from "../AdministrationFilters";
import "@testing-library/jest-dom";

// The bulk upload and template download pages are routed but have no
// other entry point, so these two links are the whole way in. They spent
// months commented out behind a "temporary" change, which left the
// feature reachable only by typing the URL.
describe("AdministrationFilters", () => {
  const renderFilters = () =>
    render(
      <MemoryRouter>
        <AdministrationFilters />
      </MemoryRouter>
    );

  test("links to the bulk upload page", () => {
    renderFilters();
    expect(screen.getByRole("link", { name: /Bulk Upload/i })).toHaveAttribute(
      "href",
      "/control-center/master-data/administration/upload"
    );
  });

  test("links to the template download page", () => {
    renderFilters();
    expect(screen.getByRole("link", { name: /Download/i })).toHaveAttribute(
      "href",
      "/control-center/master-data/administration/download"
    );
  });

  test("keeps the add link", () => {
    renderFilters();
    expect(screen.getByRole("link", { name: /Add/i })).toHaveAttribute(
      "href",
      "/control-center/master-data/administration/add"
    );
  });
});
