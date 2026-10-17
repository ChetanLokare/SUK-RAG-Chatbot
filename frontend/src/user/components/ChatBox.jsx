import { useState } from "react";
import { sendMessage } from "../api/chat";
import styles from "./ChatBox.module.css";
import CitationPanel from "./CitationPanel";
import Message from "./Message";

export default function ChatBox() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [citations, setCitations] = useState([]);
  const [verified, setVerified] = useState(false);
  const [warning, setWarning] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [darkMode, setDarkMode] = useState(true);

  const submit = async () => {
    const trimmed = input.trim();

    if (!trimmed || loading) return;

    setError("");
    setWarning("");

    const updatedMessages = [
      ...messages,
      { role: "user", text: trimmed }
    ];

    // Optimistic update
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await sendMessage({
        question: trimmed,
        history: updatedMessages
      });

      if (!res || !res.answer) {
        throw new Error("Invalid response");
      }

      setMessages(prev => [
        ...prev,
        { role: "bot", text: res.answer }
      ]);

      setCitations(res.citations || []);
      setVerified(res.verified || false);
      setWarning(res.warning || "");

    } catch (err) {
      console.error("Chat error:", err);
      setError("⚠️ Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`${styles.wrapper} ${darkMode ? styles.dark : ""}`}>
      
      {/* Header */}
      <div className={styles.header}>
        <h2>SUK Knowledge Assistant</h2>

        <button
          className={styles.themeToggle}
          onClick={() => setDarkMode(!darkMode)}
        >
          {darkMode ? "☀ Light" : "🌙 Dark"}
        </button>
      </div>

      {/* Chat Area */}
      <div className={styles.chatArea}>
        {messages.map((m, i) => (
          <Message key={i} role={m.role} text={m.text} />
        ))}

        {loading && (
          <Message role="bot" text="Thinking..." />
        )}
      </div>

      {/* Error */}
      {error && (
        <div className={styles.error}>
          {error}
        </div>
      )}

      {/* Warning */}
      {warning && (
        <div className={styles.warning}>
          ⚠️ {warning}
        </div>
      )}

      {/* Citations */}
      <CitationPanel
        citations={citations}
        verified={verified}
      />

      {/* Input Area */}
      <div className={styles.inputArea}>
        <input
          value={input}
          disabled={loading}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about exams, admissions, results..."
          onKeyDown={e => e.key === "Enter" && submit()}
        />

        <button
          onClick={submit}
          disabled={loading}
        >
          {loading ? "..." : "Ask"}
        </button>
      </div>
    </div>
  );
}
