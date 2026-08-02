'use client';

import { ConfigProvider } from '@arco-design/web-react';
import type { ReactNode } from 'react';

export default function Providers({ children }: { children: ReactNode }) {
  return <ConfigProvider>{children}</ConfigProvider>;
}
