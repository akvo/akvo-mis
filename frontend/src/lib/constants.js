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

export const ARF_CASCASE_URLS = [
  {
    name: "Administration",
    endpoint: "/api/v1/public/administrations",
    initial: 1,
    list: "children",
  },
];

export const REGISTRATION_FORM = 1;
export const MONITORING_FORM = 2;
