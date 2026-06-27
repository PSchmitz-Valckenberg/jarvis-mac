import { useEffect, useRef } from "react";

function roleLabel(role) {
  if (role === "user") return "YOU";
  if (role === "assistant") return "JARVIS";
  return "SYS";
}

export default function ChatLog({ log }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [log]);

  return (
    <div className="chat-log">
      {log.length === 0 && <div className="chat-empty">// AWAITING INPUT</div>}
      {log.map((entry, i) => (
        <div key={i} className={`chat-entry role-${entry.role}`}>
          <span className="chat-role">{roleLabel(entry.role)}</span>
          <span className="chat-text">{entry.text}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
