import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";

const ChatbotMessages = ({ messages, loading, pageLabel }) => {
  const bottomRef = useRef(null);

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
              <span className="chip">What can I do on this page?</span>
              <span className="chip">How do I create a form?</span>
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
                <ReactMarkdown>{msg.content}</ReactMarkdown>
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
