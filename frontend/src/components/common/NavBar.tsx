import { Link, useLocation } from "react-router-dom";

type NavItem = {
  label: string;
  to: string;
};

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/" },
  { label: "New Meeting", to: "/new" },
];

export default function NavBar() {
  const location = useLocation();

  return (
    <nav className="mi-nav" aria-label="Primary">
      {navItems.map((item) => {
        const active =
          item.to === "/"
            ? location.pathname === "/"
            : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);

        return (
          <Link key={item.to} to={item.to} className={active ? "mi-nav-link active" : "mi-nav-link"}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
