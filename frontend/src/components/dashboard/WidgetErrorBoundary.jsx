import React from "react";
import PropTypes from "prop-types";

class WidgetErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // eslint-disable-next-line no-console
    console.error("WidgetErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      const { text } = this.props;
      return (
        <div className="dashboard-view-cell-note">
          <div>{text?.dashboardWidgetNoData || "No data available"}</div>
        </div>
      );
    }
    return this.props.children;
  }
}

WidgetErrorBoundary.propTypes = {
  children: PropTypes.node,
  text: PropTypes.object,
};

export default WidgetErrorBoundary;
