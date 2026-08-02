'use client';

import { useState } from 'react';
import { Card, Form, Input, Button, Message } from '@arco-design/web-react';
import { useRouter } from 'next/navigation';
import { setToken } from '@/lib/api-client';

export default function LoginPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (values: { token: string }) => {
    setLoading(true);
    try {
      // 通过调用 /api/codes 验证 token 是否正确
      const res = await fetch('/api/codes?page=1&pageSize=1', {
        headers: { Authorization: `Bearer ${values.token}` },
      });

      if (res.status === 401) {
        Message.error('管理密钥错误');
        return;
      }

      const data = await res.json();
      if (data.code === 0) {
        setToken(values.token);
        Message.success('登录成功');
        router.push('/codes');
      } else {
        Message.error(data.message || '登录失败');
      }
    } catch {
      Message.error('网络错误，请检查服务是否正常');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0d1117 0%, #1d2129 50%, #2c3e5e 100%)',
      }}
    >
      <Card
        style={{
          width: 400,
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 56,
            height: 56,
            borderRadius: 14,
            background: 'linear-gradient(135deg, #165dff 0%, #4080ff 100%)',
            marginBottom: 16,
            boxShadow: '0 4px 12px rgba(22,93,255,0.3)',
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style={{ width: 28, height: 28 }}>
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1d2129' }}>
            激活码管理后台
          </h1>
          <p style={{ color: '#86909c', marginTop: 6, fontSize: 13 }}>
            请输入管理密钥登录
          </p>
        </div>

        <Form form={form} onSubmit={handleSubmit} layout="vertical">
          <Form.Item
            label="管理密钥"
            field="token"
            rules={[{ required: true, message: '请输入管理密钥' }]}
          >
            <Input.Password placeholder="请输入 ADMIN_TOKEN" size="large" />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              long
              size="large"
              loading={loading}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
