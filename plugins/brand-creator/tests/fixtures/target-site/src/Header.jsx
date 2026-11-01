import { Link } from "react-router-dom";

export function Header({ user, items, onMenu }) {
  const [q, setQ] = useState("");
  return (
    <header data-cy="site-header">
      <Link to="/pricing" data-testid="nav-pricing">Pricing</Link>
      <a href={`/account/${user.id}`}>Account</a>
      <button onClick={() => onMenu({ open: true })} type="button">Menu</button>
      <input name="q" id="search-box" />
      {items.map((i) => <li key={i} id="item-static" />)}
    </header>
  );
}
