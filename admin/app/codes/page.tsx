'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Table,
  Button,
  Card,
  Form,
  Input,
  Select,
  Modal,
  Tag,
  Space,
  Message,
  Typography,
} from '@arco-design/web-react';
import type { ColumnProps } from '@arco-design/web-react/es/Table';
import { apiFetch, isLoggedIn } from '@/lib/api-client';
import type { ActivationCode, ApiResponse, PageResult } from '@/lib/types';

const { Text } = Typography;

// 格式化日期时间
function formatDateTime(dt: string | null): string {
  if (!dt) return '-';
  const d = new Date(dt);
  if (isNaN(d.getTime())) return dt;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function CodesPage() {
  const [data, setData] = useState<ActivationCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [filters, setFilters] = useState({
    status: '',
    type: '',
    keyword: '',
  });

  // 创建弹窗
  const [createVisible, setCreateVisible] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);
  const [createType, setCreateType] = useState<string>('permanent');

  // 编辑弹窗
  const [editVisible, setEditVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [editRecord, setEditRecord] = useState<ActivationCode | null>(null);
  const [editing, setEditing] = useState(false);

  // 创建结果弹窗
  const [resultVisible, setResultVisible] = useState(false);
  const [resultCodes, setResultCodes] = useState<string[]>([]);

  const router = useRouter();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pagination.current),
        pageSize: String(pagination.pageSize),
      });
      if (filters.status) params.set('status', filters.status);
      if (filters.type) params.set('type', filters.type);
      if (filters.keyword) params.set('keyword', filters.keyword);

      const res = await apiFetch<ApiResponse<PageResult<ActivationCode>>>(
        `/api/codes?${params.toString()}`
      );
      if (res.code === 0) {
        setData(res.data.list);
        setPagination((prev) => ({ ...prev, total: res.data.total }));
      }
    } catch {
      // apiFetch 已处理错误跳转
    } finally {
      setLoading(false);
    }
  }, [pagination.current, pagination.pageSize, filters]);

  // 鉴权检查
  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace('/login');
      return;
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchData]);

  // 创建激活码
  const handleCreate = async () => {
    try {
      const values = await createForm.validate();
      setCreating(true);
      const res = await apiFetch<ApiResponse<{ codes: string[] }>>('/api/codes', {
        method: 'POST',
        body: JSON.stringify({
          type: values.type,
          days: values.type === 'day' ? Number(values.days) : 0,
          count: Number(values.count),
          remark: values.remark || '',
        }),
      });
      if (res.code === 0) {
        Message.success(res.message);
        setCreateVisible(false);
        createForm.resetFields();
        setResultCodes(res.data.codes);
        setResultVisible(true);
        fetchData();
      } else {
        Message.error(res.message);
      }
    } catch {
      // 表单校验失败
    } finally {
      setCreating(false);
    }
  };

  // 编辑备注
  const handleEdit = async () => {
    try {
      const values = await editForm.validate();
      setEditing(true);
      const res = await apiFetch<ApiResponse<null>>(`/api/codes/${editRecord?.id}`, {
        method: 'PUT',
        body: JSON.stringify({ remark: values.remark }),
      });
      if (res.code === 0) {
        Message.success('修改成功');
        setEditVisible(false);
        fetchData();
      } else {
        Message.error(res.message);
      }
    } catch {
      // 表单校验失败
    } finally {
      setEditing(false);
    }
  };

  // 解绑
  const handleUnbind = (record: ActivationCode) => {
    Modal.confirm({
      title: '确认解绑',
      content: `确定要解绑激活码 ${record.code} 吗？解绑后该激活码将恢复为未使用状态。`,
      okText: '确认解绑',
      cancelText: '取消',
      onOk: async () => {
        try {
          const res = await apiFetch<ApiResponse<null>>(
            `/api/codes/${record.id}/unbind`,
            { method: 'POST' }
          );
          if (res.code === 0) {
            Message.success('解绑成功');
            fetchData();
          } else {
            Message.error(res.message);
          }
        } catch {
          Message.error('操作失败');
        }
      },
    });
  };

  // 删除
  const handleDelete = (record: ActivationCode) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除激活码 ${record.code} 吗？此操作不可撤销。`,
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { status: 'danger' },
      onOk: async () => {
        try {
          const res = await apiFetch<ApiResponse<null>>(`/api/codes/${record.id}`, {
            method: 'DELETE',
          });
          if (res.code === 0) {
            Message.success('删除成功');
            fetchData();
          } else {
            Message.error(res.message);
          }
        } catch {
          Message.error('操作失败');
        }
      },
    });
  };

  // 打开编辑弹窗
  const openEdit = (record: ActivationCode) => {
    setEditRecord(record);
    setEditVisible(true);
    // 等 Modal 渲染后再设置表单值
    setTimeout(() => {
      editForm.setFieldsValue({ remark: record.remark || '' });
    }, 50);
  };

  // 筛选搜索
  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    fetchData();
  };

  // 重置筛选
  const handleReset = () => {
    setFilters({ status: '', type: '', keyword: '' });
    setPagination((prev) => ({ ...prev, current: 1 }));
  };

  const columns: ColumnProps[] = [
    {
      title: '序号',
      width: 70,
      render: (_col, _record, index) =>
        (pagination.current - 1) * pagination.pageSize + index + 1,
    },
    {
      title: '激活码',
      dataIndex: 'code',
      width: 200,
      render: (code) => <Text copyable>{code}</Text>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      width: 90,
      render: (type: string) =>
        type === 'day' ? (
          <Tag color="arcoblue">按天</Tag>
        ) : (
          <Tag color="purple">永久</Tag>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (status: string) => {
        const map: Record<string, { text: string; color: string }> = {
          unused: { text: '未使用', color: 'green' },
          bound: { text: '已绑定', color: 'arcoblue' },
          disabled: { text: '已禁用', color: 'red' },
        };
        const item = map[status] || { text: status, color: 'gray' };
        return <Tag color={item.color}>{item.text}</Tag>;
      },
    },
    {
      title: '设备类型',
      dataIndex: 'device_type',
      width: 90,
      render: (v: string | null) =>
        v ? (v === 'win' ? 'Windows' : 'macOS') : '-',
    },
    {
      title: '设备码',
      dataIndex: 'device_id',
      width: 140,
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    {
      title: '绑定时间',
      dataIndex: 'bound_at',
      width: 170,
      render: (v: string | null) => formatDateTime(v),
    },
    {
      title: '有效期',
      dataIndex: 'expires_at',
      width: 170,
      render: (v: string | null, record: ActivationCode) => {
        if (record.type === 'permanent') {
          return <span style={{ color: '#86909c' }}>永久</span>;
        }
        if (!v) {
          // 按天类型但未绑定：显示天数
          return <span style={{ color: '#86909c' }}>{record.days} 天</span>;
        }
        // 已绑定：显示过期时间
        const exp = new Date(v);
        if (isNaN(exp.getTime())) return '-';
        const now = new Date();
        const daysLeft = Math.ceil((exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
        if (daysLeft <= 0) {
          return <span style={{ color: '#f53f3f' }}>已过期</span>;
        }
        return <span style={{ color: daysLeft <= 3 ? '#ff7d00' : '#00b42a' }}>{daysLeft} 天剩余</span>;
      },
    },
    {
      title: '备注',
      dataIndex: 'remark',
      width: 130,
      ellipsis: true,
      render: (v: string) => v || <span style={{ color: '#c9cdd4' }}>-</span>,
    },
    {
      title: '修改时间',
      dataIndex: 'updated_at',
      width: 160,
      render: (v: string | null) => formatDateTime(v),
    },
    {
      title: '操作',
      width: 200,
      fixed: 'right',
      render: (_col, record: ActivationCode) => (
        <Space size="small">
          {record.status === 'bound' && (
            <Button
              size="mini"
              status="warning"
              onClick={() => handleUnbind(record)}
            >
              解绑
            </Button>
          )}
          <Button size="mini" type="text" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            size="mini"
            type="text"
            status="danger"
            onClick={() => handleDelete(record)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 20 }}>
      {/* 筛选区域 */}
      <Card style={{ marginBottom: 16 }}>
        <div
          style={{
            display: 'flex',
            gap: 12,
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <Space size="small">
            <Select
              placeholder="状态筛选"
              allowClear
              style={{ width: 140 }}
              value={filters.status || undefined}
              onChange={(v) => setFilters((prev) => ({ ...prev, status: v || '' }))}
            >
              <Select.Option value="unused">未使用</Select.Option>
              <Select.Option value="bound">已绑定</Select.Option>
              <Select.Option value="disabled">已禁用</Select.Option>
            </Select>
            <Select
              placeholder="类型筛选"
              allowClear
              style={{ width: 140 }}
              value={filters.type || undefined}
              onChange={(v) => setFilters((prev) => ({ ...prev, type: v || '' }))}
            >
              <Select.Option value="day">按天</Select.Option>
              <Select.Option value="permanent">永久</Select.Option>
            </Select>
            <Input
              placeholder="搜索激活码"
              allowClear
              style={{ width: 220 }}
              value={filters.keyword}
              onChange={(v) =>
                setFilters((prev) => ({ ...prev, keyword: v }))
              }
              onPressEnter={handleSearch}
            />
            <Button type="primary" onClick={handleSearch}>
              查询
            </Button>
            <Button onClick={handleReset}>重置</Button>
          </Space>
          <div style={{ flex: 1 }} />
          <Button
            type="primary"
            onClick={() => {
              createForm.resetFields();
              setCreateType('permanent');
              setCreateVisible(true);
            }}
          >
            创建激活码
          </Button>
        </div>
      </Card>

      {/* 表格 */}
      <Card>
        <Table
          columns={columns}
          data={data}
          loading={loading}
          rowKey="id"
          scroll={{ x: 1700 }}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showTotal: true,
            onChange: (page, pageSize) => {
              setPagination((prev) => ({
                ...prev,
                current: page,
                pageSize,
              }));
            },
          }}
        />
      </Card>

      {/* 创建弹窗 */}
      <Modal
        title="创建激活码"
        visible={createVisible}
        onCancel={() => setCreateVisible(false)}
        footer={null}
        maskClosable={false}
      >
        <Form
          form={createForm}
          layout="vertical"
          onSubmit={handleCreate}
          initialValues={{ type: 'permanent', days: 30, count: 1 }}
        >
          <Form.Item
            label="类型"
            field="type"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select
              onChange={(v) => setCreateType(v)}
              placeholder="请选择类型"
            >
              <Select.Option value="permanent">永久</Select.Option>
              <Select.Option value="day">按天</Select.Option>
            </Select>
          </Form.Item>

          {createType === 'day' && (
            <Form.Item
              label="有效天数"
              field="days"
              rules={[
                { required: true, message: '请输入天数' },
                {
                  validator: (value, callback) => {
                    if (value && Number(value) > 0) {
                      callback();
                    } else {
                      callback('天数必须大于 0');
                    }
                  },
                },
              ]}
            >
              <Input placeholder="请输入有效天数" type="number" />
            </Form.Item>
          )}

          <Form.Item
            label="生成数量"
            field="count"
            rules={[
              { required: true, message: '请输入数量' },
              {
                validator: (value, callback) => {
                  const n = Number(value);
                  if (n >= 1 && n <= 100) {
                    callback();
                  } else {
                    callback('数量范围 1-100');
                  }
                },
              },
            ]}
          >
            <Input placeholder="1-100" type="number" />
          </Form.Item>

          <Form.Item label="备注" field="remark">
            <Input.TextArea placeholder="可选备注信息" maxLength={255} showWordLimit />
          </Form.Item>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button onClick={() => setCreateVisible(false)}>取消</Button>
            <Button type="primary" htmlType="submit" loading={creating}>
              创建
            </Button>
          </div>
        </Form>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title="编辑备注"
        visible={editVisible}
        onCancel={() => setEditVisible(false)}
        footer={null}
        maskClosable={false}
      >
        <Form form={editForm} layout="vertical" onSubmit={handleEdit}>
          <Form.Item label="激活码">
            <Input value={editRecord?.code || ''} disabled />
          </Form.Item>
          <Form.Item
            label="备注"
            field="remark"
            rules={[{ maxLength: 255, message: '备注最多 255 字符' }]}
          >
            <Input.TextArea placeholder="请输入备注" maxLength={255} showWordLimit />
          </Form.Item>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button onClick={() => setEditVisible(false)}>取消</Button>
            <Button type="primary" htmlType="submit" loading={editing}>
              保存
            </Button>
          </div>
        </Form>
      </Modal>

      {/* 创建结果弹窗 */}
      <Modal
        title="创建成功"
        visible={resultVisible}
        onCancel={() => setResultVisible(false)}
        footer={
          <Button type="primary" onClick={() => setResultVisible(false)}>
            确定
          </Button>
        }
        maskClosable={false}
      >
        <p style={{ marginBottom: 12 }}>
          成功生成 {resultCodes.length} 个激活码：
        </p>
        <div
          style={{
            background: '#f5f5f5',
            padding: 16,
            borderRadius: 8,
            maxHeight: 300,
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: 14,
            lineHeight: '1.8',
          }}
        >
          {resultCodes.map((code, i) => (
            <div key={i}>
              {i + 1}. <Text copyable>{code}</Text>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
