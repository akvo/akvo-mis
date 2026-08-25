import React, { useRef, useEffect } from "react";
import { SendOutlined } from "@ant-design/icons";

const ChatbotInput = ({ input, setInput, onSend, loading }) => {
  const inputRef = useRef(null);

  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !loading) {
        onSend();
      }
    }
  };

  return (
    <div className="chatbot-input-container">
      <textarea
        ref={inputRef}
        className="chatbot-input-textarea"
        rows={1}
        placeholder="Ask a question..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <button
        type="button"
        className={`chatbot-send-btn ${
          input.trim() && !loading ? "active" : ""
        }`}
        onClick={onSend}
        disabled={!input.trim() || loading}
        aria-label="Send Message"
      >
        <SendOutlined />
      </button>
    </div>
  );
};

export default ChatbotInput;
