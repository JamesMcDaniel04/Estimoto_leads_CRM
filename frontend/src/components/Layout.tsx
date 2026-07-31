import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Calendar, Inbox, Kanban, LogOut, Users } from "lucide-react";
import { clearToken } from "../lib/api";

const navItems = [
  { to: "/", label: "Pipeline", icon: Kanban, end: true },
  { to: "/leads", label: "Leads", icon: Users, end: false },
  { to: "/inbox", label: "Email Inbox", icon: Inbox, end: false },
  { to: "/meetings", label: "Meetings", icon: Calendar, end: false },
];

export default function Layout() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 py-5">
          <div className="text-lg font-bold tracking-tight">Estimoto</div>
          <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Leads CRM
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={() => {
            clearToken();
            navigate("/login");
          }}
          className="mx-3 mb-4 flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </aside>
      <main className="flex-1 overflow-x-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
