import type { Metadata } from 'next';
import './globals.css';
import '@arco-design/web-react/dist/css/arco.css';
import Providers from './providers';
import Sidebar from './components/Sidebar';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: '激活码管理后台',
  description: 'Activation Code Admin System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <div style={{ display: 'flex', minHeight: '100vh' }}>
            <Sidebar />
            <main style={{ flex: 1, overflow: 'auto', background: '#f5f5f5' }}>
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
