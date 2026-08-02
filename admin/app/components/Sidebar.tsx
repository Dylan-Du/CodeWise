'use client';

import { usePathname, useRouter } from 'next/navigation';
import { Menu } from '@arco-design/web-react';

const MenuItem = Menu.Item;

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  // 登录页不显示侧边栏
  if (pathname === '/login') return null;

  const selectedKey = pathname.startsWith('/codes')
    ? 'codes'
    : pathname.startsWith('/logs')
    ? 'logs'
    : 'codes';

  const handleClick = (key: string) => {
    router.push(`/${key}`);
  };

  return (
    <aside
      style={{
        width: 220,
        background: '#1d2129',
        color: '#c9cdd4',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Logo 区域 */}
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          justifyContent: 'center',
          borderBottom: '1px solid #2c2f33',
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="#165dff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style={{ width: 24, height: 24 }}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        <span style={{ fontSize: 16, fontWeight: 600, color: '#fff' }}>激活码管理</span>
      </div>

      {/* 菜单 */}
      <Menu
        theme="dark"
        selectedKeys={[selectedKey]}
        onClickMenuItem={handleClick}
        style={{ flex: 1, background: 'transparent', borderRight: 'none', paddingTop: 8 }}
      >
        <MenuItem key="codes">
          <span style={{ marginRight: 8, display: 'inline-flex', verticalAlign: 'middle' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style={{ width: 18, height: 18 }}>
              <rect x="3" y="4" width="18" height="16" rx="2" ry="2"></rect>
              <line x1="3" y1="10" x2="21" y2="10"></line>
              <line x1="8" y1="14" x2="16" y2="14"></line>
            </svg>
          </span>
          激活码管理
        </MenuItem>
        <MenuItem key="logs">
          <span style={{ marginRight: 8, display: 'inline-flex', verticalAlign: 'middle' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style={{ width: 18, height: 18 }}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="9" y1="13" x2="15" y2="13"></line>
              <line x1="9" y1="17" x2="13" y2="17"></line>
            </svg>
          </span>
          日志管理
        </MenuItem>
      </Menu>

      {/* 底部 */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: '1px solid #2c2f33',
          fontSize: 12,
          color: '#86909c',
          textAlign: 'center',
        }}
      >
        Codex助手 v1.0.0
      </div>
    </aside>
  );
}
