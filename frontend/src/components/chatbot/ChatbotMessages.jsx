import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";

const getSuggestions = (pageLabel) => {
  const lower = (pageLabel || "").toLowerCase();
  if (lower.includes("form")) {
    return [
      "What can I do on this page?",
      "How do I add a repeatable question group?",
      "How do I configure skip logic and conditions?",
    ];
  }
  if (lower.includes("data") || lower.includes("submission")) {
    return [
      "What can I do on this page?",
      "How do I filter and export data?",
      "How do data approvals work?",
    ];
  }
  if (lower.includes("approval") || lower.includes("control center")) {
    return [
      "What can I do on this page?",
      "How do I configure approval rules?",
      "How do administrative levels work?",
    ];
  }
  return [
    "What can I do on this page?",
    "How do I create a form?",
    "What question types are available in Akvo MIS?",
  ];
};

const ChatbotMessages = ({
  messages,
  loading,
  pageLabel,
  onSelectSuggestion,
}) => {
  const bottomRef = useRef(null);
  const suggestions = getSuggestions(pageLabel);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="chatbot-messages-list">
      {messages.length === 0 && (
        <div className="chatbot-empty-state">
          <div className="chatbot-welcome-icon">
            <RobotOutlined />
          </div>
          <h4>Hi! I&apos;m Mira 👋</h4>
          <p>
            Your Akvo MIS assistant. Ask me anything about{" "}
            <strong>{pageLabel}</strong> or general platform features!
          </p>
          <div className="chatbot-suggestions">
            <div className="suggestion-title">Suggested questions:</div>
            <div className="suggestion-chips">
              {suggestions.map((question) => (
                <button
                  type="button"
                  key={question}
                  className="chip"
                  onClick={() => onSelectSuggestion?.(question)}
                  disabled={loading}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`chatbot-message-row ${
            msg.role === "user" ? "user-row" : "assistant-row"
          }`}
        >
          <div className="chatbot-avatar">
            {msg.role === "user" ? <UserOutlined /> : <RobotOutlined />}
          </div>
          <div className="chatbot-bubble">
            {msg.role === "assistant" ? (
              <div className="chatbot-markdown-body">
                <ReactMarkdown>
                  {(msg.content || "").replace(/【.*?】/g, "").trim()}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="chatbot-user-text">{msg.content}</div>
            )}
          </div>
        </div>
      ))}

      {loading && (
        <div className="chatbot-message-row assistant-row">
          <div className="chatbot-avatar">
            <RobotOutlined />
          </div>
          <div className="chatbot-bubble typing-bubble">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

export default ChatbotMessages;
