import { Link, useLocation } from "react-router-dom";

type SidebarItem = {
    name: string;
    href: string;
};

const navigation: SidebarItem[] = [
    { name: "Dashboard", href: "/" },
    { name: "New meeting", href: "/new" },
];

export default function Sidebar() {
    const location = useLocation();

    return (
        <aside className="mi-sidebar" aria-label="Sidebar">
            <h3>Workspace</h3>
            <nav>
                {navigation.map((item) => {
                    const isActive =
                        item.href === "/"
                            ? location.pathname === "/"
                            : location.pathname === item.href || location.pathname.startsWith(`${item.href}/`);

                    return (
                        <Link key={item.name} to={item.href} className={isActive ? "mi-sidebar-link active" : "mi-sidebar-link"}>
                            {item.name}
                        </Link>
                    );
                })}
            </nav>
        </aside>
    );
}