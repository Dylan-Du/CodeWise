'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Button,
  Card,
  Input,
  Tag,
  Space,
  Message,
} from '@arco-design/web-react';
import type { ColumnProps } from '@arco-design/web-react/es/Table';
import { apiFetch, isLoggedIn } from '@/lib/api-client';
import type { ActivationLog, ApiResponse, PageResult } from '@/lib/types';
import { useRouter } from 'next/navigation';

function formatDateTime(dt: string | null): string {
  if (!dt) return '-';
  const d = new Date(dt);
  if (isNaN(d.getTime())) return dt;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// 解析详情文本，提取错误信息
function parseErrorDetail(detail: string | null): { model: string; message: string; fullDetail: string } {
  if (!detail) return { model: '-', message: '-', fullDetail: '-' };
  // 后台存储格式是文本：错误类型: xxx\n错误消息: xxx\n详细信息: xxx...
  const lines = detail.split('\n');
  let errorType = '-';
  let errorMsg = '-';
  let model = '-';
  for (const line of lines) {
    if (line.startsWith('错误类型:')) errorType = line.substring(5).trim();
    else if (line.startsWith('错误消息:')) errorMsg = line.substring(5).trim();
    else if (line.startsWith('模型:')) model = line.substring(3).trim();
  }
  // 如果错误消息包含 [model] 前缀
  const modelMatch = errorMsg.match(/^\[([^\]]+)\]/);
  if (modelMatch) {
    model = modelMatch[1];
    errorMsg = errorMsg.substring(modelMatch[0].length).trim();
  }
  return {
    model: model !== '-' ? model : errorType,
    message: errorMsg,
    fullDetail: detail,
  };
}

export default function ErrorsPage() {
  const router = useRouter();
  const [data, setData] = useState<ActivationLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [keyword, setKeyword] = useState('');
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pagination.current),
        pageSize: String(pagination.pageSize),
        action: 'error',
      });
      if (keyword) params.set('keyword', keyword);

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
  }, [pagination.current, pagination.pageSize, keyword]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace('/login');
      return;
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchData]);

  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    fetchData();
  };

  const toggleExpand = (id: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const columns: ColumnProps[] = [
    {
      title: '序号',
      width: 60,
      render: (_col, _record, index) =>
        (pagination.current - 1) * pagination.pageSize + index + 1,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '设备',
      width: 100,
      render: (_col, record) => {
        const dt = record.device_type;
        return dt ? (dt === 'win' ? 'Windows' : 'macOS') : '-';
      },
    },
    {
      title: '设备码',
      dataIndex: 'device_id',
      width: 120,
      ellipsis: true,
      render: (v: string | null) => v ? v.substring(0, 16) + '...' : '-',
    },
    {
      title: '错误信息',
      width: 350,
      render: (_col, record) => {
        const parsed = parseErrorDetail(record.detail);
        return (
          <div>
            {parsed.model !== '-' && (
              <Tag color="purple" style={{ marginBottom: 4 }}>{parsed.model}</Tag>
            )}
            <div style={{ fontSize: 13, color: '#f53f3f', wordBreak: 'break-all' }}>
              {parsed.message}
            </div>
          </div>
        );
      },
    },
    {
      title: '操作',
      width: 80,
      render: (_col, record) => (
        <Button
          type="text"
          size="small"
          onClick={() => toggleExpand(record.id)}
        >
          {expandedRows.has(record.id) ? '收起' : '详情'}
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 20 }}>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Space size="small">
            <Input
              placeholder="搜索错误信息或设备码"
              allowClear
              style={{ width: 300 }}
              value={keyword}
              onChange={(v) => setKeyword(v)}
              onPressEnter={handleSearch}
            />
            <Button type="primary" onClick={handleSearch}>查询</Button>
            <Button onClick={() => { setKeyword(''); setPagination((prev) => ({ ...prev, current: 1 })); }}>刷新</Button>
          </Space>
        </div>
      </Card>

      <Card>
        <Table
          columns={columns}
          data={data}
          loading={loading}
          rowKey="id"
          scroll={{ x: 900 }}
          expandedRowKeys={Array.from(expandedRows)}
          expandedRowRender={(record) => (
            <pre style={{
              background: '#1d2129',
              color: '#c9cdd4',
              padding: 12,
              borderRadius: 6,
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              maxHeight: 400,
              overflow: 'auto',
            }}>
              {record.detail || '无详细信息'}
            </pre>
          )}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showTotal: true,
            onChange: (page, pageSize) => {
              setPagination((prev) => ({ ...prev, current: page, pageSize }));
            },
          }}
        />
      </Card>
    </div>
  );
}
