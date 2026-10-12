import { useState } from "react";
import { api, store, uiText } from "../../lib";
import { useNotification } from "../../util/hooks";
import { workspaceUrl } from "../../util/tenant";

// Opening a workspace is a hand-off, not a link. Only the console's host
// can mint the one-time code, and the workspace's own /inspect spends
// it, so an anchor to that address would arrive carrying no credential
// and be refused. Both places that offer Inspect -- the list and the
// detail page -- do exactly this, and do it through here so they cannot
// drift apart.
//
// `inspecting` is the id being opened, so a caller can put a spinner on
// the one control the operator clicked rather than on all of them.
const useInspect = () => {
  const [inspecting, setInspecting] = useState(null);
  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const text = uiText[language.active];

  const inspect = (tenant) => {
    setInspecting(tenant.id);
    api
      .post(`admin/tenants/${tenant.id}/inspect`)
      .then((res) => {
        window.location.replace(
          `${workspaceUrl(tenant.subdomain)}/inspect?code=${res.data.code}`
        );
      })
      .catch(() => {
        setInspecting(null);
        notify({ type: "error", message: text.consoleInspectFailed });
      });
  };

  return { inspect, inspecting };
};

export default useInspect;
