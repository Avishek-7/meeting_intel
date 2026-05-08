import type { ReactNode } from "react";
import Background from "./Background";
import Header from "./Header";
import NavBar from "./NavBar";
import Sidebar from "./Sidebar";
import Footer from "./Footer";

interface LayoutProps {
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  showSidebar?: boolean;
  showTopNav?: boolean;
  children: ReactNode;
}

export default function Layout({
  title,
  subtitle,
  headerRight,
  showSidebar = false,
  showTopNav,
  children,
}: LayoutProps) {
  const shouldShowTopNav = showTopNav ?? !showSidebar;

  return (
    <Background>
      <div className="mi-shell">
        <Header title={title} subtitle={subtitle} rightContent={headerRight} />
        {shouldShowTopNav ? <NavBar /> : null}

        <div className={showSidebar ? "mi-content with-sidebar" : "mi-content"}>
          {showSidebar ? <Sidebar /> : null}
          <main className="mi-main" role="main">
            {children}
          </main>
        </div>

        <Footer />
      </div>
    </Background>
  );
}
