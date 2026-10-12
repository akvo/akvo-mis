import React, { useEffect, useState } from "react";
import PropTypes from "prop-types";
import { Modal, Input, Alert, Form } from "antd";
import { api } from "../../lib";
import { useNotification } from "../../util/hooks";
import { baseDomain } from "../../util/tenant";

const RenameModal = ({ tenant, open, onClose, onRenamed }) => {
  const { notify } = useNotification();
  const [impact, setImpact] = useState(null);
  const [subdomain, setSubdomain] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    // Cleared on every open, not just the first. TenantDetail mounts
    // this dialog permanently and only toggles `open`, so without this
    // an operator who typed the confirmation and then cancelled would
    // find the danger-red button already armed next time they opened it
    // to read the impact — one click from the rename they came back to
    // reconsider. The re-typing is the guard; it has to be re-earned.
    setImpact(null);
    setSubdomain("");
    setConfirmation("");
    api
      .get(`admin/tenants/${tenant.id}/rename-impact`)
      .then((res) => setImpact(res.data))
      .catch(() => setImpact(false));
  }, [open, tenant.id]);

  // Three conditions, all required. A new address, because arming a
  // rename to nothing only buys a 400 the operator cannot interpret.
  // The typed confirmation guards against a mis-click. And the loaded
  // impact guards against renaming behind an unknown consequence, which
  // is the failure this dialog exists to prevent — so an unreachable
  // preflight disables the action rather than waving it through.
  const armed =
    Boolean(subdomain.trim()) &&
    Boolean(impact) &&
    confirmation === tenant.subdomain;

  const submit = () => {
    setSaving(true);
    api
      .post(`admin/tenants/${tenant.id}/rename`, { subdomain })
      .then((res) => {
        onRenamed(res.data);
        onClose();
      })
      .catch((err) =>
        notify({
          type: "error",
          message:
            err?.response?.data?.message || "Could not rename the workspace",
        })
      )
      .finally(() => setSaving(false));
  };

  return (
    <Modal
      open={open}
      title="Rename workspace"
      onCancel={onClose}
      onOk={submit}
      okText="Rename workspace"
      okButtonProps={{ danger: true, disabled: !armed, loading: saving }}
    >
      <Form layout="vertical">
        {/* Explicit ids rather than antd's own: Form.Item derives
            htmlFor from a field `name`, which these controlled inputs
            do not have, so the labels would point at nothing and the
            fields would be unreachable to a screen reader. */}
        <Form.Item label="New address" htmlFor="rename-subdomain">
          <Input
            id="rename-subdomain"
            addonAfter={`.${baseDomain()}`}
            value={subdomain}
            onChange={(event) => setSubdomain(event.target.value)}
          />
        </Form.Item>

        {impact === false && (
          <Alert
            type="error"
            showIcon
            message="Could not work out what this rename would break"
            description="Renaming is blocked until the check succeeds."
          />
        )}

        {impact && (
          <Alert
            type="warning"
            showIcon
            message="The old address stops working immediately"
            description={
              <ul>
                <li>
                  <strong>{impact.published_dashboards} dashboard links</strong>
                  {" will break for anyone in the workspace who has one "}
                  {"bookmarked."}
                </li>
                <li>
                  <strong>
                    {impact.public_dashboards} publicly shared dashboards
                  </strong>
                  {" will stop loading for readers outside the workspace, "}
                  {"including any site that has framed one."}
                </li>
              </ul>
            }
          />
        )}

        <Form.Item
          label={`Type ${tenant.subdomain} to confirm`}
          htmlFor="rename-confirm"
          style={{ marginTop: 16 }}
        >
          <Input
            id="rename-confirm"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

RenameModal.propTypes = {
  tenant: PropTypes.object.isRequired,
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onRenamed: PropTypes.func.isRequired,
};

export default RenameModal;
