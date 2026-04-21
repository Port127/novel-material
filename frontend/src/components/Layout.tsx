import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Library, Search, Users, Tags, Settings,
  BookOpen, PanelLeftClose, PanelLeft, Upload,
} from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', icon: LayoutDashboard, label: '总览', end: true },
  { to: '/materials', icon: Library, label: '素材库' },
  { to: '/upload', icon: Upload, label: '上传小说' },
  { to: '/search/events', icon: Search, label: '事件搜索' },
  { to: '/search/characters', icon: Users, label: '人物搜索' },
  { to: '/tags', icon: Tags, label: '标签字典' },
  { to: '/settings', icon: Settings, label: '设置' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={cn(
          'flex flex-col border-r bg-slate-900/60 backdrop-blur-sm transition-all duration-300 shrink-0',
          collapsed ? 'w-[60px]' : 'w-56',
        )}
      >
        <div className="flex items-center gap-2.5 px-4 h-14 border-b shrink-0">
          <BookOpen className="w-5 h-5 text-amber-500 shrink-0" />
          {!collapsed && (
            <span className="font-semibold text-sm tracking-wide whitespace-nowrap">
              小说素材库
            </span>
          )}
        </div>

        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {nav.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors',
                  'hover:bg-white/5',
                  isActive
                    ? 'bg-amber-500/10 text-amber-400 font-medium'
                    : 'text-slate-400',
                )
              }
            >
              <Icon className="w-[18px] h-[18px] shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center h-10 border-t text-slate-500 hover:text-slate-300 transition-colors shrink-0"
        >
          {collapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
        </button>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="min-h-full">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
