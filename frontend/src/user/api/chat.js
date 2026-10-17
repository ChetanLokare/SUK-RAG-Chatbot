import { API } from "../../api/config";

/**
 * Ask the backend a question.
 *
 * `history` is the running chat ([{ role: "user" | "bot", text }]).
 * The backend uses it to understand follow-up questions such as
 * "and what are the fees?".
 */
export async function sendMessage({ question, history }) {
  const res = await fetch(`${API}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      history
    })
  });

  if (!res.ok) {
    throw new Error("Server error");
  }

  return res.json();
}
