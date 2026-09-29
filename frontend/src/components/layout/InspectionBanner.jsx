import React from "react";
import { Button, Space } from "antd";
import { EyeOutlined } from "@ant-design/icons";
import { useCookies } from "react-cookie";
import { store } from "../../lib";
import { eraseCookieFromAllPaths } from "../../util/date";
import { adminUrl } from "../../util/tenant";
import "./style.scss";

// When this session stops working, from the token's own `exp` claim.
// Read out of the cookie rather than from a field on the profile: the
// expiry belongs to the token, and anything the server echoed beside it
// would be a second copy to keep in step. Anything that does not parse
// gives null -- a banner without a time beats no banner.
const endsAt = (token) => {
  try {
    const { exp } = JSON.parse(atob(token.split(".")[1]));
    return exp
      ? new Date(exp * 1000).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
  } catch (err) {
    return null;
  }
};

// Deliberately loud, and deliberately the only thing inspection adds to
// a workspace's app. Everything below it is the workspace's own layout
// and components, untouched.
const InspectionBanner = () => {
  const { user, tenant } = store.useState((s) => s);
  const [cookies] = useCookies(["AUTH_TOKEN"]);

  if (!user?.is_inspecting) {
    return null;
  }

  // Erase, then leave. Staying put would re-render the workspace's own
  // pages with no session at all, which is a screen of failed requests
  // rather than a sign-out.
  const exit = () => {
    eraseCookieFromAllPaths("AUTH_TOKEN");
    window.location.replace(adminUrl("/admin/tenants"));
  };

  const ends = cookies.AUTH_TOKEN ? endsAt(cookies.AUTH_TOKEN) : null;

  return (
    <div className="inspection-banner">
      <Space size={12}>
        <EyeOutlined />
        <span>
          {"Inspecting "}
          <strong>{tenant?.subdomain}</strong>
          {" · read only"}
          {ends ? ` · ends ${ends}` : ""}
        </span>
      </Space>
      <Button size="small" onClick={exit}>
        Exit inspection
      </Button>
    </div>
  );
};

export default InspectionBanner;
