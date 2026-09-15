import React, { useState } from "react";
import { Row, Col } from "antd";
import { config } from "../../lib";

const GradationLegend = ({
  title = "",
  thresholds = [],
  colors = null,
  onClick = () => {},
}) => {
  const [shapeFilterColor, setShapeFilterColor] = useState(null);
  const colorRange = colors || config.mapConfig.colorRange;

  const handleOnClick = (index) => {
    if (shapeFilterColor === colorRange[index]) {
      setShapeFilterColor(null);
      onClick(null);
      return;
    }
    setShapeFilterColor(colorRange[index]);
    onClick(index);
  };

  const formatValue = (value) => {
    // Handle decimal values by rounding to 1 decimal place if needed
    return value % 1 !== 0 ? Number(value).toFixed(1) : value;
  };

  const renderRange = (t, tI) => {
    const formattedT = formatValue(t);

    if (tI === 0) {
      return `0 - ${formattedT}`;
    }
    if (tI >= thresholds.length - 1) {
      return `> ${formatValue(thresholds[tI - 1])}`;
    }
    const nextVal =
      thresholds[tI - 1] % 1 !== 0
        ? (Number(thresholds[tI - 1]) + 0.1).toFixed(1)
        : thresholds[tI - 1] + 1;
    return `${nextVal} - ${formattedT}`;
  };

  thresholds = [...thresholds, thresholds[thresholds.length - 1]];

  return (
    <div className="shape-legend">
      <h4>{title}</h4>
      <Row className="legend-wrap">
        {thresholds.map((t, tI) => (
          <Col
            key={tI}
            flex={1}
            className={`legend-item ${
              shapeFilterColor === colorRange[tI] ? "legend-selected" : ""
            }`}
            onClick={() => handleOnClick(tI)}
            style={{ backgroundColor: colorRange[tI] }}
          >
            {renderRange(t, tI)}
          </Col>
        ))}
      </Row>
    </div>
  );
};

export default GradationLegend;
