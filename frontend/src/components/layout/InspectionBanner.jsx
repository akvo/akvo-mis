import React, { useState } from "react";
import { Button, Dropdown, Space } from "antd";
import { DownOutlined, EyeOutlined } from "@ant-design/icons";
import { useCookies } from "react-cookie";
import { api, store } from "../../lib";
import { useNotification } from "../../util/hooks";
import { eraseCookieFromAllPaths } from "../../util/date";
import { adminUrl, workspaceUrl } from "../../util/tenant";
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
  // null means "not asked yet". Distinguishing that from an empty list
  // is what keeps the fetch to one per session.
  const [options, setOptions] = useState(null);
  const { notify } = useNotification();

  if (!user?.is_inspecting) {
    return null;
  }

  // Fetched when the dropdown is first opened rather than on mount.
  // Most sessions never switch, and an eager fetch would add one
  // request to every page of every workspace an operator visits.
  const loadOptions = () => {
    if (options) {
      return;
    }
    api
      .get("inspect/tenants")
      .then((res) =>
        setOptions(
          res.data.filter((row) => row.subdomain !== tenant?.subdomain)
        )
      )
      .catch(() => setOptions([]));
  };

  // The new workspace is a different origin, so this is a real
  // navigation: the code is minted here and spent by that host's
  // /inspect, exactly as the console's own hand-off works.
  const switchTo = ({ key }) => {
    api
      .post("inspect/switch", { tenant_id: Number(key) })
      .then((res) => {
        window.location.replace(
          `${workspaceUrl(res.data.subdomain)}/inspect?code=${res.data.code}`
        );
      })
      .catch(() =>
        notify({ type: "error", message: "Could not switch workspace" })
      );
  };

  // A menu needs items even before the answer arrives, and "none" and
  // "not yet" say different things to someone who just clicked.
  const items = options?.map((row) => ({
    key: String(row.id),
    label: (
      <span>
        <strong>{row.subdomain}</strong>
        {row.name ? ` \u00b7 ${row.name}` : ""}
      </span>
    ),
  }));
  const empty = items ? "No other workspaces" : "Loading...";
  const menu = items?.length
    ? items
    : [{ key: "empty", label: empty, disabled: true }];

  // Erase, then leave. Staying put would re-render the workspace's own
  // pages with no session at all, which is a screen of failed requests
  // rather than a sign-out.
  const exit = () => {
    eraseCookieFromAllPaths("AUTH_TOKEN");
    window.location.replace(adminUrl("/admin/tenants"));
  };

  const ends = endsAt(cookies.AUTH_TOKEN);

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
      <Space size={8}>
        <Dropdown menu={{ items: menu, onClick: switchTo }} trigger={["click"]}>
          <Button size="small" onClick={loadOptions}>
            <Space size={6}>
              {"Switch workspace"}
              <DownOutlined />
            </Space>
          </Button>
        </Dropdown>
        <Button size="small" onClick={exit}>
          Exit inspection
        </Button>
      </Space>
    </div>
  );
};

export default InspectionBanner;
