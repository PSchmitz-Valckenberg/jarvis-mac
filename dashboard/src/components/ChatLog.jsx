export default function ChatLog({ log }) {
  return (
    <div className="panel" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      <p className="panel__title">
        <span>CHAT LOG</span>
        <span className="accent">LAST {log.length}</span>
      </p>
      <div className="chat-log">
        {log.length === 0 && <div className="empty-hint">Keine Nachrichten bisher.</div>}
        {log.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role} fade-in`}>
            {msg.text}
          </div>
        ))}
      </div>
    </div>
  );
}
