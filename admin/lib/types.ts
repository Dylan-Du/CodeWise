/**
 * 类型定义
 */

export interface ActivationCode {
  id: number;
  code: string;
  type: 'day' | 'permanent';
  days: number;
  status: 'unused' | 'bound' | 'disabled';
  device_type: 'win' | 'mac' | null;
  device_id: string | null;
  bound_at: string | null;
  expires_at: string | null;
  remark: string;
  created_at: string;
  updated_at: string;
}

export interface ActivationLog {
  id: number;
  code: string;
  action: string;
  device_id: string | null;
  device_type: 'win' | 'mac' | null;
  ip: string | null;
  detail: string | null;
  created_at: string;
}

export interface ApiResponse<T = unknown> {
  code: number;
  data: T;
  message: string;
}

export interface PageResult<T> {
  list: T[];
  total: number;
  page: number;
  pageSize: number;
}
