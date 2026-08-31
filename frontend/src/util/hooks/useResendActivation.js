import { useState } from "react";
import { api } from "../../lib";

// Three screens can offer to send the activation email again — the
// check-your-email state after signing up, the expired-link landing, and the
// login page when an unactivated account tries to sign in. They differ only
// in where the address comes from and what success looks like, so the request
// and its in-flight flag live here and the screens keep their own UI.
function useResendActivation() {
  const [resending, setResending] = useState(false);

  const resend = (email) => {
    setResending(true);
    return api.post("register/resend-activation", { email }).finally(() => {
      setResending(false);
    });
  };

  return { resend, resending };
}

export default useResendActivation;
