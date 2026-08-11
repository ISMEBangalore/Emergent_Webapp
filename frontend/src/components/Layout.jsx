import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ChartBar, UploadSimple, ClockCounterClockwise, GearSix, GraduationCap, List, X } from "@phosphor-icons/react";

const nav = [
  { to: "/", label: "Dashboard", icon: ChartBar, testid: "nav-dashboard" },
  { to: "/generate", label: "Generate Report", icon: UploadSimple, testid: "nav-generate" },
  { to: "/history", label: "History", icon: ClockCounterClockwise, testid: "nav-history" },
  { to: "/settings", label: "Settings", icon: GearSix, testid: "nav-settings" },
];

const Brand = () => (
  <div className="flex items-center gap-2.5">
    <div className="h-9 w-9 rounded-md bg-[#002FA7] flex items-center justify-center">
      <GraduationCap size={22} weight="fill" color="#fff" />
    </div>
    <div>
      <p className="font-display font-extrabold text-slate-900 leading-tight tracking-tight">LeadPulse</p>
      <p className="text-[11px] text-slate-400 tracking-wide uppercase">Weekly CRM Reports</p>
    </div>
  </div>
);

export const Layout = ({ children }) => {
  const loc = useLocation();
  const [open, setOpen] = useState(false);

  const NavLinks = ({ onClick }) => (
    <>
      {nav.map((n) => {
        const Icon = n.icon;
        const active = n.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(n.to);
        return (
          <NavLink
            key={n.to}
            to={n.to}
            data-testid={n.testid}
            onClick={onClick}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
              active ? "bg-[#002FA7] text-white" : "text-slate-600 hover:bg-slate-100 hover:text-[#002FA7]"
            }`}
          >
            <Icon size={19} weight={active ? "fill" : "regular"} />
            {n.label}
          </NavLink>
        );
      })}
    </>
  );

  return (
    <div className="min-h-screen bg-[#F8F9FA]">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-slate-200 bg-white flex-col fixed h-screen z-20">
        <div className="px-6 py-6 border-b border-slate-200"><Brand /></div>
        <nav className="flex-1 px-3 py-4 space-y-1"><NavLinks /></nav>
        <div className="px-6 py-4 border-t border-slate-200 text-[11px] text-slate-400">Data source: merrito.com CRM</div>
      </aside>

      {/* Mobile top bar */}
      <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between px-4 py-3 bg-white border-b border-slate-200">
        <Brand />
        <button data-testid="mobile-menu-btn" onClick={() => setOpen(true)} className="p-2 text-slate-600">
          <List size={24} weight="bold" />
        </button>
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-64 bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <Brand />
              <button onClick={() => setOpen(false)} className="p-1 text-slate-500"><X size={22} weight="bold" /></button>
            </div>
            <nav className="space-y-1"><NavLinks onClick={() => setOpen(false)} /></nav>
          </div>
        </div>
      )}

      <main className="lg:ml-64 min-h-screen">{children}</main>
    </div>
  );
};
