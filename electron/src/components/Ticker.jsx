export default function Ticker({ message }) {
  return (
    <div className="ticker">
      <span className="ticker-tag">STATUS</span>
      <span className="ticker-text">{message}</span>
    </div>
  );
}
