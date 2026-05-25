import api from "./api";

const config = {
  siteLogo: "/logo.svg",
  trainedStatus: [
    {
      label: "Trained",
      value: true,
    },
    {
      label: "Not Trained",
      value: false,
    },
  ],
  organisationAttributes: [
    {
      id: 1,
      name: "User Organisation",
    },
    {
      id: 2,
      name: "Partnership Organisation",
    },
  ],
  approvalsLiteral: (props = { isButton: false }) => {
    return props?.isButton ? "Approve" : "Approvals";
  },
  templates: [
    {
      id: 1,
      formId: 519630048,
      name: "Template 1",
      title: "Sanitation Service Levels",
      charts: [
        {
          type: "PIE",
          id: 513690068,
          title: "Functional Toilet Available",
        },
        {
          type: "BAR",
          id: 492490054,
          title: "Kind of Toilet Facility",
        },
        {
          type: "CRITERIA",
          title: "Sanitation Service Level",
          options: [
            {
              name: "Safely Managed",
              color: "#368541",
              score: 15,
              options: [
                {
                  question: 492490054,
                  option: [
                    "Flush / pour flush",
                    "Pit latrine with slab",
                    "Twin pit with slab",
                  ],
                },
                {
                  question: 513690062,
                  option: ["No"],
                },
                {
                  question: 513690060,
                  option: [
                    "Removed by service provider to a treatment plant",
                    "Removed by service provider to buried pit",
                    "Emptied by household buried in a covered pit",
                  ],
                },
              ],
            },
            {
              name: "Basic",
              score: 10,
              color: "#79BE7D",
              options: [
                {
                  question: 492490054,
                  option: [
                    "Flush / pour flush",
                    "Pit latrine with slab",
                    "Twin pit with slab",
                  ],
                },
                {
                  question: 513690062,
                  option: ["No"],
                },
              ],
            },
            {
              name: "Limited",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 492490054,
                  option: [
                    "Flush / pour flush",
                    "Pit latrine with slab",
                    "Twin pit with slab",
                  ],
                },
                {
                  question: 513690062,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "Unimproved",
              score: -2,
              color: "#FBD256",
              options: [
                {
                  question: 492490054,
                  option: [
                    "Pit latrine without slab / Open pit",
                    "Twin pit without slab",
                    "Bucket",
                    "Hanging toilet / hanging latrine",
                  ],
                },
              ],
            },
            {
              name: "Open Defecation",
              score: -3,
              // title: "OD",
              color: "#F1AC2A",
              options: [
                {
                  question: 492490054,
                  option: ["No facility / Bush / Field"],
                },
              ],
            },
          ],
          // stack: {
          //   options: [
          //     {
          //       name: "805",
          //       title: "805, Baringo", // Eg. Override administration name
          //     },
          //   ],
          // },
        },
      ],
      description:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 1",
        description:
          "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },
    {
      id: 2,
      formId: 519630048,
      name: "Template 2",
      title: "Hygiene Service Levels",
      charts: [
        {
          type: "CRITERIA",
          title: "Hygiene Service Level",
          options: [
            {
              name: "Basic",
              score: 10,
              color: "#753780",
              options: [
                {
                  question: 466680043,
                  option: [
                    "Fixed facility observed (sink/tap) In dwelling",
                    "Fixed facility observed (sink/tap)  In yard/plot",
                    "Mobile object observed (bucket/jug/kettle)",
                  ],
                },
                {
                  question: 466680045,
                  option: ["Water is available"],
                },
                {
                  question: 466760036,
                  option: ["Soap or detergent available ."],
                },
              ],
            },
            {
              name: "Limited",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 466680043,
                  option: [
                    "Fixed facility observed (sink/tap) In dwelling",
                    "Fixed facility observed (sink/tap)  In yard/plot",
                    "Mobile object observed (bucket/jug/kettle)",
                  ],
                },
                {
                  question: 466680045,
                  option: ["Water is available"],
                },
                {
                  question: 466760036,
                  option: ["Soap or detergent available ."],
                },
              ],
            },
            {
              name: "No Facility",
              score: -2,
              color: "#F1AC2A",
              options: [
                {
                  question: 466680043,
                  option: [
                    "No handwashing place in dwelling/yard/plot",
                    "No permission to see",
                  ],
                },
              ],
            },
          ],
        },
      ],
      description:
        "Consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 2",
        description:
          "Consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },
    {
      id: 3,
      formId: 519630048,
      name: "Template 3",
      title: "Menstrual Hygiene Service Levels",
      charts: [
        {
          type: "CRITERIA",
          title: "Menstrual Hygiene",
          options: [
            {
              name: "Awareness",
              color: "#368541",
              score: 15,
              options: [],
            },
            {
              name: "Use of mensrual materials",
              score: 10,
              color: "#79BE7D",
              options: [
                // {
                //   question: 524810053,
                //   option: [
                //     "Attending school",
                //     "Paid work",
                //     "Participating in social activities",
                //     "Cooking food?"
                //   ]
                // },
              ],
            },
            {
              name: "Access",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 524810054,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "Participation",
              score: -2,
              color: "#FBD256",
              options: [
                {
                  question: 524810053,
                  option: [
                    "Attending school",
                    "Paid work",
                    "Participating in social activities",
                    "Cooking food?",
                    "Cooking food",
                    "Eating with others",
                    "Bathing in regular place",
                  ],
                },
              ],
            },
          ],
        },
      ],
      description:
        "Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 3",
        description:
          "Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },

    {
      id: 4,
      formId: 533560002,
      name: "Template 1",
      title: "Sanitation",
      charts: [
        {
          type: "CRITERIA",
          title: "Sanitation",
          options: [
            {
              name: "Basic",
              color: "#368541",
              score: 15,
              options: [
                {
                  question: 555370004,
                  option: [
                    "Flush / Pour-flush toilet to sewer connection",
                    "Flush / Pour-flush toilet to tank or pit",
                    "Pit latrine with slab",
                    "Composting toilet",
                  ],
                },
                {
                  question: 530250002,
                  option: ["Yes"],
                },
                {
                  question: 555370009,
                  option: ["Yes"],
                },
                {
                  question: 555370003,
                  option: ["Yes"],
                },
                {
                  question: 555370005,
                  option: ["Yes"],
                },
                {
                  question: 555370006,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "Limited",
              score: 10,
              color: "#79BE7D",
              options: [
                {
                  question: 555370004,
                  option: [
                    "Flush / Pour-flush toilet to sewer connection",
                    "Flush / Pour-flush toilet to tank or pit",
                    "Pit latrine with slab",
                    "Composting toilet",
                  ],
                },
                {
                  question: 530250002,
                  option: ["No"],
                },
                {
                  question: 555370009,
                  option: ["No"],
                },
                {
                  question: 555370003,
                  option: ["No"],
                },
                {
                  question: 555370005,
                  option: ["No"],
                },
                {
                  question: 555370006,
                  option: ["No"],
                },
              ],
            },
            {
              name: "No service",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 555370004,
                  option: [
                    "Flush / Pour-flush toilet to open drain",
                    "Pit latrine without slab/open pit",
                    "Bucket",
                    "Hanging toilet/latrine",
                    "No toilet/latrine",
                  ],
                },
              ],
            },
          ],
        },
      ],
      description:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 1",
        description:
          "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },
    {
      id: 5,
      formId: 533560002,
      name: "Template 2",
      title: "Hygiene (Hand washing)",
      charts: [
        {
          type: "CRITERIA",
          title: "Hygiene (Hand washing)",
          options: [
            {
              name: "Basic",
              color: "#368541",
              score: 15,
              options: [
                {
                  question: 551560007,
                  option: ["Yes"],
                },
                {
                  question: 551560004,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "Limited",
              score: 10,
              color: "#79BE7D",
              options: [
                {
                  question: 551560007,
                  option: [
                    "No, there are hand hygiene facilities at points of care but not functional, or lacking soap and water or alcohol-based hand rub.",
                  ],
                },
                {
                  question: 551560004,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "No service",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 551560007,
                  option: [
                    "No, there are hand hygiene facilities at points of care but not functional, or lacking soap and water or alcohol-based hand rub.",
                    "No, no hand hygiene facilities at points of care",
                  ],
                },
                {
                  question: 551560004,
                  option: [
                    "No, there are handwashing facilities near the toilets but lacking soap and/or water",
                    "No, no handwashing facilities near toilets (within 5 meters)",
                  ],
                },
              ],
            },
          ],
        },
      ],
      description:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 1",
        description:
          "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },

    {
      id: 6,
      formId: 563350033,
      name: "Template 1",
      title: "Drinking water",
      charts: [
        {
          type: "CRITERIA",
          title: "Drinking water",
          options: [
            {
              name: "Basic",
              score: 10,
              color: "#753780",
              options: [
                {
                  question: 551660011,
                  option: [
                    "Piped water supply",
                    "Protected well/spring",
                    "Rainwater",
                    "Unprotected well/spring",
                    "Packaged bottled water",
                  ],
                },
                {
                  question: 551660013,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "Limited",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 551660011,
                  option: [
                    "Piped water supply",
                    "Protected well/spring",
                    "Rainwater",
                    "Unprotected well/spring",
                    "Packaged bottled water",
                  ],
                },
                {
                  question: 551660013,
                  option: ["No"],
                },
              ],
            },
            {
              name: "No Service",
              score: -2,
              color: "#F1AC2A",
              options: [
                {
                  question: 551660011,
                  option: [
                    "Tanker-truck or cart",
                    "Surface water (lake, river, stream)",
                    "No water source",
                  ],
                },
              ],
            },
          ],
        },
      ],
      description:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 1",
        description:
          "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },
    {
      id: 7,
      formId: 563350033,
      name: "Template 2",
      title: "Sanitation",
      charts: [
        {
          type: "CRITERIA",
          title: "Sanitation",
          options: [
            {
              name: "Basic",
              score: 10,
              color: "#753780",
              options: [
                {
                  question: 551660029,
                  option: [
                    "Flush / Pour-flush toilets",
                    "Pit latrines with slab",
                    "Composting toilets",
                  ],
                },
                {
                  question: 579840064,
                  option: ["Yes"],
                },
                {
                  question: 555460003,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "Limited",
              score: -1,
              color: "#FDF177",
              options: [
                {
                  question: 551660029,
                  option: [
                    "Flush / Pour-flush toilets",
                    "Pit latrines with slab",
                    "Composting toilets",
                  ],
                },
                {
                  question: 579840064,
                  option: ["Yes"],
                },
                {
                  question: 555460003,
                  option: ["Yes"],
                },
              ],
            },
            {
              name: "No Service",
              score: -2,
              color: "#F1AC2A",
              options: [
                {
                  question: 551660029,
                  option: [
                    "Pit latrines without slab",
                    "Hanging latrines",
                    "Bucket latrines",
                    "No toilets or latrines",
                  ],
                },
              ],
            },
          ],
        },
      ],
      description:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      footer: {
        title: "Footer title 1",
        description:
          "Lorem ipsum dolor sit amet consectetur adipisicing elit. Unde, sunt corrupti fuga facilis non illo eos. Quae optio illum doloribus provident, non esse libero modi excepturi porro ducimus, voluptatibus tenetur!",
      },
    },
  ],
  allowedGlobal: ["/dashboard/", "/glaas/"],
  fn: {
    administration: (id, withchildren = true) => {
      return new Promise((resolve, reject) => {
        api
          .get(`administration/${id}`)
          .then((res) => {
            if (!withchildren) {
              delete res.data.children;
              resolve(res.data);
            } else {
              resolve(res.data);
            }
          })
          .catch((error) => {
            reject(error);
          });
      });
    },
    ls: {
      set: (name, data) => {
        localStorage.setItem(name, JSON.stringify(data));
      },
      get: (name) => {
        if (localStorage.getItem(name)) {
          return JSON.parse(localStorage.getItem(name));
        }
        return false;
      },
    },
  },
  attribute: {
    allTypes: [
      {
        value: "value",
        label: "Value",
      },
      {
        value: "option",
        label: "Option",
      },
      {
        value: "multiple_option",
        label: "Multiple Option",
      },
      {
        value: "aggregate",
        label: "Aggregate",
      },
    ],
    optionTypes: ["option", "multiple_option", "aggregate"],
  },
  maxLevelApproval: 3,
  minEntityLevel: 0,
  batchAttachment: {
    allowed: [
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/csv",
      "application/zip",
      "application/x-zip-compressed",
      "application/x-rar-compressed",
      "application/x-7z-compressed",
      "application/x-tar",
      "application/x-gzip",
      "application/vnd.oasis.opendocument.text",
      "application/vnd.oasis.opendocument.spreadsheet",
      ".ods",
      ".odt",
    ],
    maxSize: 10, // 10 MB
  },
  mapConfig: {
    defaultZoom: 6,
    defaultCenter: [0, 0],
    markerSizeRange: [10, 50],
    highlightColor: "#84b4cc",
    colorRange: ["#e8f7e3", "#bbedda", "#7dcaaf", "#44a883", "#107550"],
  },
};

export default config;
