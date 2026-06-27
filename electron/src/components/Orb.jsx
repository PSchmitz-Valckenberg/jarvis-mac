export default function Orb({ state }) {
  return (
    <div className="orb-column">
      <div className={`orb-wrap state-${state}`}>
        <div className="orb-ring ring3" />
        <div className="orb-ring ring2" />
        <div className="orb-ring ring1" />
        <div className="orb-core" />
      </div>
      <div className="state-label">{state.toUpperCase()}</div>
    </div>
  );
}
