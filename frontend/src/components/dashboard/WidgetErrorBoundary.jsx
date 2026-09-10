import React from "react";
import PropTypes from "prop-types";
import { Button } from "antd";

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

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      const { text } = this.props;
      return (
        <div className="dashboard-view-cell-note">
          <div>{text?.dashboardWidgetError || "Couldn't load this widget"}</div>
          <Button type="link" size="small" onClick={this.handleRetry}>
            {text?.dashboardWidgetRetry || "Retry"}
          </Button>
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
