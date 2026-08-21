import React, { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import {
  MessageOutlined,
  CloseOutlined,
  ReloadOutlined,
  CompassOutlined,
} from "@ant-design/icons";
import { api, store } from "../../lib";
import ChatbotMessages from "./ChatbotMessages";
import ChatbotInput from "./ChatbotInput";
import "./chatbot.scss";

const STORAGE_THREAD_KEY = "akvo_mis_chat_thread_id";
const STORAGE_MESSAGES_KEY = "akvo_mis_chat_messages";

// Derive human-readable page context on frontend for live context chip
const derivePageLabel = (pathname) => {
  if (!pathname || pathname === "/") {
    return "General Platform";
  }
  const clean = pathname.split("?")[0].replace(/^\//, "").replace(/\/$/, "");

  if (clean === "data") {
    return "Data Management";
  }
  if (clean === "control-center") {
    return "Control Center";
  }

  const cleanPath = clean.replace(/^(control-center|data)\/?/, "");

  const segments = cleanPath
    .split("/")
    .filter((s) => s && !/^\d+$/.test(s) && !/^[0-9a-f-]{36}$/i.test(s))
    .map((s) => s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));

  return segments.length > 0 ? segments.join(" — ") : "General Platform";
};

const ChatbotWidget = () => {
  const location = useLocation();
  const { user: authUser } = store.useState((state) => state);

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_MESSAGES_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState(() => {
    return sessionStorage.getItem(STORAGE_THREAD_KEY) || null;
  });

  const currentPageLabel = derivePageLabel(location.pathname);

  // Sync messages to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_MESSAGES_KEY, JSON.stringify(messages));
    } catch {
      // Ignore sessionStorage quota errors
    }
  }, [messages]);

  // Sync thread_id to sessionStorage
  useEffect(() => {
    if (threadId) {
      sessionStorage.setItem(STORAGE_THREAD_KEY, threadId);
    }
  }, [threadId]);

  const handleSendMessage = useCallback(
    async (customText = null) => {
      const textToSend = customText || input.trim();
      if (!textToSend || loading) {
        return;
      }

      const userMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: textToSend,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setLoading(true);

      try {
        const payload = {
          message: textToSend,
          page_url: location.pathname,
          ...(threadId ? { thread_id: threadId } : {}),
        };

        const res = await api.post("chatbot/message", payload);
        const data = res?.data || {};

        if (data.thread_id && !threadId) {
          setThreadId(data.thread_id);
        }

        const botMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response || "No response received.",
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, botMessage]);
      } catch {
        const errorMessage = {
          id: `error-${Date.now()}`,
          role: "assistant",
          content:
            "Sorry, I was unable to connect to the knowledge base. Please try again.",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, location.pathname, threadId]
  );

  const handleClearChat = () => {
    setMessages([]);
    setThreadId(null);
    sessionStorage.removeItem(STORAGE_MESSAGES_KEY);
    sessionStorage.removeItem(STORAGE_THREAD_KEY);
  };

  // Only render if user is authenticated
  if (!authUser) {
    return null;
  }

  return (
    <div className="akvo-chatbot-wrapper">
      {/* Floating Action Button */}
      <button
        type="button"
        className={`chatbot-fab-btn ${isOpen ? "open" : ""}`}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label="Open AI Assistant"
      >
        {isOpen ? <CloseOutlined /> : <MessageOutlined />}
        {!isOpen && <span className="chatbot-fab-pulse" />}
      </button>

      {/* Collapsible Chat Panel */}
      {isOpen && (
        <div className="chatbot-panel-card">
          {/* Header */}
          <div className="chatbot-header">
            <div className="chatbot-header-info">
              <div className="persona-title">
                <span className="online-status-dot" />
                <span className="persona-name">Mira</span>
                <span className="persona-badge">MIS Assistant</span>
              </div>
              <div className="context-chip" title="Current Page Context">
                <CompassOutlined />
                <span>{currentPageLabel}</span>
              </div>
            </div>

            <div className="chatbot-header-actions">
              <button
                type="button"
                className="header-icon-btn"
                onClick={handleClearChat}
                title="Start New Conversation"
                aria-label="Reset Conversation"
              >
                <ReloadOutlined />
              </button>
              <button
                type="button"
                className="header-icon-btn"
                onClick={() => setIsOpen(false)}
                title="Close"
                aria-label="Close Assistant"
              >
                <CloseOutlined />
              </button>
            </div>
          </div>

          {/* Message Stream */}
          <ChatbotMessages
            messages={messages}
            loading={loading}
            pageLabel={currentPageLabel}
          />

          {/* Input Area */}
          <ChatbotInput
            input={input}
            setInput={setInput}
            onSend={() => handleSendMessage()}
            loading={loading}
          />
        </div>
      )}
    </div>
  );
};

export default ChatbotWidget;
