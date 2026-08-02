import { NextRequest, NextResponse } from 'next/server';

/**
 * 校验后台 API 的 Authorization header
 * 所有 /api/codes 和 /api/logs 接口需要此鉴权
 */
export function checkAuth(req: NextRequest): boolean {
  const token = process.env.ADMIN_TOKEN || '';
  if (!token) return false;

  const auth = req.headers.get('authorization') || req.headers.get('Authorization');
  if (!auth) return false;

  // 支持 "Bearer <token>" 和直接 token 两种格式
  const parts = auth.split(' ');
  if (parts.length === 2 && parts[0] === 'Bearer') {
    return parts[1] === token;
  }
  return auth === token;
}

/**
 * 返回未授权响应
 */
export function unauthorized() {
  return NextResponse.json(
    { code: 401, data: null, message: '未授权，请检查 Token' },
    { status: 401 }
  );
}
