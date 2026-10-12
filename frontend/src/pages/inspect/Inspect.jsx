import React, { useEffect, useState } from "react";
import { Result, Spin } from "antd";
import { useSearchParams } from "react-router-dom";
import { api } from "../../lib";

// Where the console's one-time code becomes a session. The exchange
// sets AUTH_TOKEN itself, so there is nothing to store here -- a full
// reload lets the app bootstrap as it always does.
const Inspect = () => {
  const [params] = useSearchParams();
  const [failed, setFailed] = useState(false);
  const code = params.get("code");

  useEffect(() => {
    if (!code) {
      setFailed(true);
      return;
    }
    api
      .post("inspect/exchange", { code })
      .then(() => {
        window.location.replace("/control-center");
      })
      .catch(() => setFailed(true));
  }, [code]);

  if (failed) {
    return (
      <Result
        status="error"
        title="This inspection link has expired or has already been used"
        subTitle="Open the workspace again from the platform console."
      />
    );
  }
  return <Spin />;
};

export default Inspect;
