import { NextResponse } from 'next/server';

/**
 * 统一成功响应
 */
export function success(data: unknown = null, message: string = '') {
  return NextResponse.json({ code: 0, data, message });
}

/**
 * 统一错误响应
 */
export function error(message: string = '操作失败', code: number = -1, status: number = 200) {
  return NextResponse.json({ code, data: null, message }, { status });
}
