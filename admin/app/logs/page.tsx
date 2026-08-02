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
  DatePicker,
  Message,
} from '@arco-design/web-react';
import type { ColumnProps } from '@arco-design/web-react/es/Table';
import { apiFetch, isLoggedIn } from '@/lib/api-client';
import type { ActivationLog, ApiResponse, PageResult } from '@/lib/types';
import { useRouter } from 'next/navigation';

const { RangePicker } = DatePicker;

// 格式化日期时间
function formatDateTime(dt: string | null): string {
  if (!dt) return '-';
  const d = new Date(dt);
  if (isNaN(d.getTime())) return dt;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// 操作类型标签映射
const ACTION_MAP: Record<string, { text: string; color: string }> = {
  bind: { text: '绑定', color: 'arcoblue' },
  unbind: { text: '解绑', color: 'orange' },
  verify: { text: '验证', color: 'green' },
  create: { text: '创建', color: 'purple' },
  delete: { text: '删除', color: 'red' },
  edit: { text: '编辑', color: 'cyan' },
  error: { text: '错误', color: 'red' },
};

export default function LogsPage() {
  const router = useRouter();
  const [data, setData] = useState<ActivationLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [filters, setFilters] = useState({
    action: '',
    keyword: '',
    startDate: '',
    endDate: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pagination.current),
        pageSize: String(pagination.pageSize),
      });
      if (filters.action) params.set('action', filters.action);
      if (filters.keyword) params.set('keyword', filters.keyword);
      if (filters.startDate) params.set('startDate', filters.startDate);
      if (filters.endDate) params.set('endDate', filters.endDate);

      const res = await apiFetch<ApiResponse<PageResult<ActivationLog>>>(
        `/api/logs?${params.toString()}`
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

  // 筛选搜索
  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    fetchData();
  };

  // 重置筛选
  const handleReset = () => {
    setFilters({ action: '', keyword: '', startDate: '', endDate: '' });
    setPagination((prev) => ({ ...prev, current: 1 }));
  };

  // 处理日期范围变化
  const handleDateChange = (dates: any) => {
    if (dates && dates.length === 2) {
      const start = dates[0];
      const end = dates[1];
      const formatDate = (d: any) => {
        if (!d) return '';
        const dt = new Date(d);
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
      };
      setFilters((prev) => ({
        ...prev,
        startDate: formatDate(start),
        endDate: formatDate(end),
      }));
    } else {
      setFilters((prev) => ({
        ...prev,
        startDate: '',
        endDate: '',
      }));
    }
  };

  const columns: ColumnProps[] = [
    {
      title: '序号',
      width: 70,
      render: (_col, _record, index) =>
        (pagination.current - 1) * pagination.pageSize + index + 1,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '激活码',
      dataIndex: 'code',
      width: 200,
    },
    {
      title: '操作类型',
      dataIndex: 'action',
      width: 100,
      render: (action: string) => {
        const item = ACTION_MAP[action] || { text: action, color: 'gray' };
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
      title: 'IP 地址',
      dataIndex: 'ip',
      width: 140,
      render: (v: string | null) => v || '-',
    },
    {
      title: '详情',
      dataIndex: 'detail',
      width: 300,
      render: (v: string | null) =>
        v ? (
          <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: 12 }}>
            {v}
          </span>
        ) : '-',
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
          <Space size="small" wrap>
            <Select
              placeholder="操作类型"
              allowClear
              style={{ width: 140 }}
              value={filters.action || undefined}
              onChange={(v) => setFilters((prev) => ({ ...prev, action: v || '' }))}
            >
              {Object.entries(ACTION_MAP).map(([key, val]) => (
                <Select.Option key={key} value={key}>
                  {val.text}
                </Select.Option>
              ))}
            </Select>
            <Input
              placeholder="搜索激活码"
              allowClear
              style={{ width: 220 }}
              value={filters.keyword}
              onChange={(v) => setFilters((prev) => ({ ...prev, keyword: v }))}
              onPressEnter={handleSearch}
            />
            <RangePicker
              style={{ width: 260 }}
              onChange={handleDateChange}
              placeholder={['开始日期', '结束日期']}
            />
            <Button type="primary" onClick={handleSearch}>
              查询
            </Button>
            <Button onClick={handleReset}>重置</Button>
          </Space>
        </div>
      </Card>

      {/* 表格 */}
      <Card>
        <Table
          columns={columns}
          data={data}
          loading={loading}
          rowKey="id"
          scroll={{ x: 1200 }}
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
    </div>
  );
}
