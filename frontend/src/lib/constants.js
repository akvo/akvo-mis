export const IMAGE_EXTENSIONS = [
  "jpg",
  "jpeg",
  "png",
  "gif",
  "bmp",
  "tiff",
  "webp",
  "heif",
  "heic",
  "svg",
  "ico",
];
export const QUESTION_TYPES = {
  input: "input",
  text: "text",
  number: "number",
  date: "date",
  image: "image",
  geo: "geo",
  option: "option",
  multiple_option: "multiple_option",
  cascade: "cascade",
  entity: "entity",
  autofield: "autofield",
  attachment: "attachment",
  signature: "signature",
};

export const READ_ACCESS = 1;
export const APPROVE_ACCESS = 2;
export const SUBMIT_ACCESS = 3;
export const EDIT_ACCESS = 4;
export const DELETE_ACCESS = 5;

export const ACCESS_LEVELS = {
  [READ_ACCESS]: "Read",
  [APPROVE_ACCESS]: "Approve",
  [SUBMIT_ACCESS]: "Submit",
  [EDIT_ACCESS]: "Edit",
  [DELETE_ACCESS]: "Delete",
};

export const ACCESS_LEVELS_LIST = Object.entries(ACCESS_LEVELS).map(
  ([key, value]) => ({
    key: parseInt(key, 10),
    value,
  })
);

export const APPROVAL_STATUS_PENDING = 1;
export const APPROVAL_STATUS_APPROVED = 2;
export const APPROVAL_STATUS_REJECTED = 3;

// The administration cascade for the form builder. It used to point at a
// token-less /public/administrations, which handed every tenant's units to
// anyone; that endpoint is gone. akvo-react-form threads `headers` into its
// axios.get, so the cascade can use the authenticated, tenant-scoped
// endpoint instead. It has to be built per render rather than kept as a
// module constant: it needs the live token, and `initial` must be the
// caller's own root, not a hardcoded 1.
export const buildAdministrationCascade = (token, rootId) => [
  {
    name: "Administration",
    endpoint: "/api/v1/administration",
    initial: rootId,
    list: "children",
    headers: { Authorization: `Bearer ${token}` },
  },
];

export const REGISTRATION_FORM = 1;
export const MONITORING_FORM = 2;
