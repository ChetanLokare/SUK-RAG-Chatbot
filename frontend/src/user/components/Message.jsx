import ReactMarkdown from "react-markdown";
import styles from "./ChatBox.module.css";

export default function Message({ role, text }) {
  const isUser = role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text || "");
    } catch (err) {
      console.error("Copy failed:", err);
    }
  };

  return (
    <div
      className={`${styles.messageRow} ${
        isUser ? styles.userRow : styles.botRow
      }`}
    >
      <div
        className={`${styles.messageBubble} ${
          isUser ? styles.userBubble : styles.botBubble
        }`}
      >
        <div className={styles.messageHeader}>
          <span className={styles.senderLabel}>
            {isUser ? "You" : "SUK Assistant"}
          </span>

          {!isUser && (
            <button
              className={styles.copyBtn}
              onClick={handleCopy}
              title="Copy answer"
            >
              📋
            </button>
          )}
        </div>

        <div className={styles.messageContent}>
          <ReactMarkdown>
            {text || ""}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
