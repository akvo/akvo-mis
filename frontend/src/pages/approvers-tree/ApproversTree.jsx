import React, { useState, useEffect, useMemo, useCallback } from "react";
import "./style.scss";
import { Row, Col, Space, Dropdown } from "antd";
import { Breadcrumbs, DescriptionPanel } from "../../components";
import { api, config, store, uiText } from "../../lib";
import ApproverFilters from "../../components/filters/ApproverFilters";
import { SteppedLineTo } from "react-lineto";
import { takeRight } from "lodash";
import { useNotification } from "../../util/hooks";
import { InfoCircleOutlined } from "@ant-design/icons";
import { getLevels } from "../../util/level";

const ApproversTree = () => {
  const {
    administration: filterOption,
    user: authUser,
    forms,
    selectedForm,
  } = store.useState((s) => s);

  const administration = useMemo(() => {
    return filterOption.filter((item) => item.level <= config.maxLevelApproval);
  }, [filterOption]);

  const [nodes, setNodes] = useState([]);
  const [dataset, setDataset] = useState([]);
  const [datasetJson, setDatasetJson] = useState("[]");
  const [scroll, setScroll] = useState(0);
  const [loading, setLoading] = useState(false);
  const { notify } = useNotification();
  const { language } = store.useState((s) => s);
  const { active: activeLang } = language;
  const text = useMemo(() => {
    return uiText[activeLang];
  }, [activeLang]);

  const pagePath = [
    {
      title: text.controlCenter,
      link: "/control-center",
    },
    {
      title: text.manageDataValidationSetup,
    },
  ];

  const startingLevel = getLevels().find(
    (l) => l.level === authUser?.administration?.level + 1
  );

  useEffect(() => {
    setNodes([
      {
        id: 0,
        name: "Questionnaire",
        children: forms
          .filter((f) => !f?.content?.parent)
          .map((dt) => ({
            ...dt,
            users: null,
            active: false,
          })),
      },
    ]);
  }, [forms]);

  useEffect(() => {
    if (!!administration.length && selectedForm) {
      const selectedAdministration = takeRight(administration, 1)[0];
      setLoading(true);
      api
        .get(
          `form/approver/?administration_id=${selectedAdministration?.id}&form_id=${selectedForm}`
        )
        .then((res) => {
          setDataset((prev) => {
            // Create deep clone of previous state
            let adminClone = JSON.parse(JSON.stringify(prev));

            // Update users data in prev state with data from res.data
            adminClone = adminClone.map((admin) => ({
              ...admin,
              children:
                admin?.children?.map((child) => {
                  // Find matching child in res.data
                  const resChild = res.data.find(
                    (rc) => rc.administration.id === child.administration.id
                  );
                  if (resChild) {
                    return {
                      ...child,
                      users: resChild.users || child.users || [],
                    };
                  }
                  return child;
                }) || [],
            }));

            // Truncate adminClone to the appropriate length
            adminClone.length = administration.length - 1;
            adminClone = [
              ...adminClone,
              {
                id: selectedAdministration?.id,
                childLevelName:
                  selectedAdministration?.childLevelName ||
                  selectedAdministration?.children_level_name,
                children: res.data.map((cI) => ({
                  ...cI,
                  users: cI?.users || [],
                })),
              },
            ];
            setDatasetJson(JSON.stringify(adminClone));
            return adminClone;
          });
          setLoading(false);
        })
        .catch(() => {
          notify({
            type: "error",
            message: "Could not fetch data",
          });
          setLoading(false);
        });
    }
  }, [administration, selectedForm, notify, startingLevel]);

  const isPristine = useMemo(() => {
    return JSON.stringify(dataset) === datasetJson;
  }, [dataset, datasetJson]);

  const handleColScroll = ({ target }) => {
    setScroll(target.scrollTop);
    const shade = takeRight(target.className.split(" "))[0];
    const shadeComponent = document.getElementById(`shade-for-${shade}`);

    if (target.scrollTop > 0) {
      shadeComponent.classList.add("on");
    } else {
      shadeComponent.classList.remove("on");
    }
  };

  const handleFormScroll = useCallback(
    ({ target }) => {
      setScroll(target.scrollTop);

      // Reset dataset to ensure synchronization when scrolling form nodes
      if (dataset.length > 0) {
        setDataset((prevDataset) => {
          const resetDataset = JSON.parse(JSON.stringify(prevDataset));
          return resetDataset;
        });
      }
    },
    [dataset]
  );

  const renderFormNodes = useMemo(() => {
    return nodes.map((nodeItem, i) => (
      <Col
        key={i}
        span={5}
        className="tree-col-0"
        align="center"
        onScroll={handleFormScroll}
      >
        {nodeItem.children.map((childItem, j) => (
          <div
            className={`tree-block tree-form-block-${childItem.id}
              ${
                childItem.id === selectedForm || nodeItem.id === selectedForm
                  ? "active"
                  : ""
              }`}
            key={j}
            onClick={() => {
              store.update((s) => {
                s.selectedForm = childItem.id;
                if (administration.length === 1) {
                  s.administration = administration.map((a) => ({
                    ...a,
                    childLevelName: a?.level_name,
                    children: [a],
                  }));
                } else {
                  s.administration = administration;
                }
              });
            }}
          >
            {childItem.name}
          </div>
        ))}
      </Col>
    ));
  }, [nodes, selectedForm, administration, handleFormScroll]);

  const renderAdminNodes = useMemo(() => {
    const handleClick = (e, index) => {
      if (!e || loading) {
        return;
      }
      setLoading(true);
      api
        .get(`administration/${e}`)
        .then((res) => {
          store.update((s) => {
            s.administration.length = index + 1;
            s.administration = [
              ...s.administration,
              {
                id: res.data.id,
                name: res.data.name,
                levelName: res.data.level_name,
                parent: res.data.parent,
                children: res.data.children,
                childLevelName: res.data.children_level_name,
                level: res.data.level,
              },
            ];
          });
          setLoading(false);
        })
        .catch(() => {
          notify({
            type: "error",
            message: "Could not load filters",
          });
          setLoading(false);
        });
    };
    return selectedForm
      ? administration.map(
          (adminItem, k) =>
            adminItem.children?.length > 0 && (
              <Col
                onScroll={handleColScroll}
                key={k}
                span={5}
                className={`tree-col-${k + 1}`}
                align="center"
              >
                {adminItem?.children?.map((childItem, l) => {
                  const approvers =
                    dataset[k]?.children?.find(
                      (c) => c.administration.id === childItem.id
                    )?.users || childItem?.users;
                  const approverName = approvers?.length
                    ? approvers?.length > 1
                      ? `${approvers[0].first_name} ${
                          approvers[0].last_name
                        } and ${approvers.length - 1} more`
                      : `${approvers[0].first_name} ${approvers[0].last_name}`
                    : text.notAssigned;
                  const isParent =
                    administration[k + 1]?.children[0]?.parent ===
                    childItem?.id;
                  const selectedAdministration = filterOption?.slice(-1)?.[0];
                  const isSelected =
                    !isParent && selectedAdministration?.id === childItem?.id;
                  const isSelectedLine = isSelected || isParent;
                  return (
                    <div
                      className={`tree-block tree-block-${k + 1}-${childItem.id}
                      ${
                        k >= administration.length - 1 || isSelectedLine
                          ? "active"
                          : ""
                      } ${approvers?.length ? "assigned" : ""}
                    `}
                      key={l}
                      onClick={() => {
                        if (
                          adminItem.levelName !==
                            takeRight(getLevels(), 2)[0]?.name &&
                          administration[k + 1]?.children[0]?.parent !==
                            childItem.id
                        ) {
                          handleClick(childItem.id, k);
                        }
                      }}
                    >
                      {approvers?.length > 0 && (
                        <div className="info-icon">
                          <Dropdown
                            menu={{
                              items: approvers.map((a) => ({
                                key: a.id,
                                label: a.email,
                              })),
                            }}
                          >
                            <InfoCircleOutlined />
                          </Dropdown>
                        </div>
                      )}
                      <Space direction="vertical">
                        <div>{childItem.name}</div>
                        <h3 className={approvers?.length ? "" : "not-assigned"}>
                          {approverName}
                        </h3>
                      </Space>
                    </div>
                  );
                })}
              </Col>
            )
        )
      : "";
  }, [
    administration,
    dataset,
    selectedForm,
    loading,
    notify,
    text.notAssigned,
    filterOption,
  ]);

  const renderFormLine = useMemo(() => {
    return (
      selectedForm &&
      !!administration.length && (
        <SteppedLineTo
          within="tree-col-0"
          key={`tree-line-${selectedForm}`}
          from={`tree-form-block-${selectedForm}`}
          to={`tree-col-0`}
          fromAnchor="right"
          toAnchor="right"
          delay={scroll ? 0 : 1}
          orientation="h"
          borderColor="#0058ff"
          borderStyle="solid"
        />
      )
    );
  }, [administration, selectedForm, scroll]);

  const renderAdminLines = useMemo(() => {
    return (
      selectedForm &&
      administration.map((adminItem, m) => (
        <div key={m}>
          {adminItem.children.map((childItem, ci) => {
            const isParent =
              administration[m + 1]?.children[0]?.parent === childItem.id;
            const selectedAdministration = filterOption?.slice(-1)?.[0];
            const isSelected =
              !isParent && selectedAdministration?.id === childItem?.id;
            const isSelectedLine = isSelected || isParent;
            return (
              <div key={ci}>
                <SteppedLineTo
                  within={`tree-col-${m + 1}`}
                  key={`tree-line-${m + 1}-${childItem.id}`}
                  from={`tree-col-${m}`}
                  to={`tree-block-${m + 1}-${childItem.id}`}
                  fromAnchor="right"
                  toAnchor="left"
                  delay={scroll ? 0 : 1}
                  orientation="h"
                  borderColor={
                    m >= administration.length - 1 || isSelectedLine
                      ? "#0058ff"
                      : "#dedede"
                  }
                  borderStyle={
                    m >= administration.length - 1 || isSelectedLine
                      ? "solid"
                      : "dotted"
                  }
                  borderWidth={
                    m >= administration.length - 1 || isSelectedLine ? 1 : 1.5
                  }
                  zIndex={
                    m >= administration.length - 1 || isSelectedLine ? 100 : 1
                  }
                />
                {isParent && (
                  <SteppedLineTo
                    within={`tree-col-${m + 1}`}
                    key={`tree-line-p-${m}-${childItem.id}`}
                    from={`tree-block-${m + 1}-${childItem.id}`}
                    to={`tree-col-${m + 2}`}
                    fromAnchor="right"
                    toAnchor="left"
                    delay={scroll ? 0 : 1}
                    orientation="h"
                    borderColor="#0058ff"
                    borderStyle="solid"
                    zIndex={100}
                  />
                )}
              </div>
            );
          })}
        </div>
      ))
    );
  }, [administration, selectedForm, scroll, filterOption]);

  return (
    <div id="approversTree">
      <div className="table-section">
        <div className="description-container">
          <Row justify="space-between">
            <Col>
              <Breadcrumbs pagePath={pagePath} />
              <DescriptionPanel
                description={text.approversDescription}
                title={text.manageDataValidationSetup}
              />
            </Col>
          </Row>
        </div>
        <div className="filters-wrapper">
          <ApproverFilters
            loading={false}
            disabled={isPristine || loading}
            visible={false}
          />
        </div>
        <div className="approvers-tree-wrapper">
          <div style={{ padding: 0, minHeight: "40vh" }}>
            <Row
              wrap={false}
              className={`tree-header ${loading ? "loading" : ""}`}
              justify="left"
            >
              <Col span={5} align="center">
                {text.questionnaireText}
              </Col>
              {selectedForm &&
                dataset.map(
                  (aN, anI) =>
                    !!aN?.children?.length && (
                      <Col key={anI} span={5} align="center">
                        {aN.childLevelName}
                        <div
                          className="shade"
                          id={`shade-for-tree-col-${anI + 1}`}
                        />
                      </Col>
                    )
                )}
            </Row>
            <div className="tree-wrap" id="tree-wrap">
              <Row wrap={false} justify="left">
                {renderFormNodes}
                {renderAdminNodes}
                {renderFormLine}
                {renderAdminLines}
              </Row>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(ApproversTree);
