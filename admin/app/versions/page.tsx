'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Button,
  Card,
  Input,
  Select,
  Tag,
  Space,
  Modal,
  Form,
  Message,
  Switch,
  Upload,
} from '@arco-design/web-react';
import type { ColumnProps } from '@arco-design/web-react/es/Table';
import { apiFetch, isLoggedIn, getToken } from '@/lib/api-client';
import type { ApiResponse } from '@/lib/types';
import { useRouter } from 'next/navigation';

interface AppVersion {
  id: number;
  version: string;
  platform: string;
  download_url: string;
  release_notes: string;
  force_update: number;
  is_latest: number;
  created_at: string;
}

function formatDateTime(dt: string | null): string {
  if (!dt) return '-';
  const d = new Date(dt);
  if (isNaN(d.getTime())) return dt;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function VersionsPage() {
  const router = useRouter();
  const [data, setData] = useState<AppVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<ApiResponse<{ list: AppVersion[] }>>('/api/versions');
      if (res.code === 0) {
        setData(res.data.list);
      }
    } catch {
      // apiFetch 已处理错误跳转
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace('/login');
      return;
    }
    fetchData();
  }, [fetchData]);

  const handleCreate = async () => {
    try {
      const values = await form.validate();
      const res = await apiFetch<ApiResponse>('/api/versions', {
        method: 'POST',
        body: JSON.stringify(values),
      });
      if (res.code === 0) {
        Message.success('版本创建成功');
        setModalVisible(false);
        form.resetFields();
        fetchData();
      } else {
        Message.error(res.message || '创建失败');
      }
    } catch {
      // 校验失败
    }
  };

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除此版本吗？',
      onOk: async () => {
        const res = await apiFetch<ApiResponse>(`/api/versions/${id}`, {
          method: 'DELETE',
        });
        if (res.code === 0) {
          Message.success('已删除');
          fetchData();
        }
      },
    });
  };

  const handleUpload = (file: File) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/versions/upload');
    xhr.setRequestHeader('Authorization', `Bearer ${getToken() || ''}`);
    xhr.onload = () => {
      setUploading(false);
      try {
        const res = JSON.parse(xhr.responseText);
        if (res.code === 0) {
          form.setFieldValue('download_url', res.data.url);
          Message.success('上传成功，下载地址已自动填入');
        } else {
          Message.error(res.message || '上传失败');
        }
      } catch {
        Message.error('上传失败');
      }
    };
    xhr.onerror = () => {
      setUploading(false);
      Message.error('上传失败，请检查网络');
    };
    xhr.send(formData);
    return false; // 阻止默认上传
  };

  const columns: ColumnProps[] = [
    {
      title: '版本号',
      dataIndex: 'version',
      width: 120,
      render: (v: string) => <Tag color="arcoblue">{v}</Tag>,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      width: 100,
      render: (v: string) => v === 'win' ? 'Windows' : 'macOS',
    },
    {
      title: '最新版',
      dataIndex: 'is_latest',
      width: 80,
      render: (v: number) => v ? <Tag color="green">最新</Tag> : '-',
    },
    {
      title: '强制更新',
      dataIndex: 'force_update',
      width: 80,
      render: (v: number) => v ? <Tag color="red">强制</Tag> : '否',
    },
    {
      title: '下载地址',
      dataIndex: 'download_url',
      width: 300,
      ellipsis: true,
      render: (v: string) => (
        <a href={v} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12 }}>
          {v}
        </a>
      ),
    },
    {
      title: '更新说明',
      dataIndex: 'release_notes',
      width: 250,
      render: (v: string | null) =>
        v ? (
          <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>{v}</span>
        ) : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 150,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '操作',
      width: 80,
      render: (_col, record: AppVersion) => (
        <Button type="text" status="danger" size="small" onClick={() => handleDelete(record.id)}>
          删除
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 20 }}>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>版本管理</h3>
          <Button type="primary" onClick={() => { form.resetFields(); setModalVisible(true); }}>
            发布新版本
          </Button>
        </div>
      </Card>

      <Card>
        <Table
          columns={columns}
          data={data}
          loading={loading}
          rowKey="id"
          scroll={{ x: 1200 }}
          pagination={false}
        />
      </Card>

      <Modal
        title="发布新版本"
        visible={modalVisible}
        onOk={handleCreate}
        onCancel={() => setModalVisible(false)}
        style={{ width: 520 }}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="版本号" field="version" rules={[{ required: true, message: '请输入版本号' }]}>
            <Input placeholder="例如: 1.0.1" />
          </Form.Item>
          <Form.Item label="平台" field="platform" rules={[{ required: true, message: '请选择平台' }]}>
            <Select placeholder="选择平台">
              <Select.Option value="mac">macOS</Select.Option>
              <Select.Option value="win">Windows</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="上传安装包">
            <Upload
              autoUpload={false}
              showUploadList={false}
              accept=".dmg,.zip,.exe,.pkg"
              beforeUpload={handleUpload}
            >
              <Button loading={uploading} type="outline">
                {uploading ? '上传中...' : '点击上传安装包 (DMG/ZIP/EXE)'}
              </Button>
            </Upload>
          </Form.Item>
          <Form.Item label="下载地址" field="download_url" rules={[{ required: true, message: '请上传安装包或填写下载地址' }]}>
            <Input placeholder="上传后自动填入，或手动填写下载地址" />
          </Form.Item>
          <Form.Item label="更新说明" field="release_notes">
            <Input.TextArea placeholder="本次更新内容..." rows={4} />
          </Form.Item>
          <Form.Item label="设为最新版" field="is_latest" triggerPropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="强制更新" field="force_update" triggerPropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
