import { MemoryRouter } from "react-router-dom";
import { CookiesProvider } from "react-cookie";
import App from "./App";

const TestApp = ({ entryPoint = "/" }) => {
  return (
    <CookiesProvider>
      <MemoryRouter initialEntries={[entryPoint]}>
        <App />
      </MemoryRouter>
    </CookiesProvider>
  );
};

export default TestApp;
