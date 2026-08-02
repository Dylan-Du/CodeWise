import { NextRequest } from 'next/server';
import pool, { addLog } from '@/lib/db';
import { success, error } from '@/lib/response';

/**
 * POST /api/activation/report-error
 * 桌面应用上报错误日志
 * Body: { code, device_id, device_type, error_type, message, details }
 * 此接口公开，无需鉴权
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { code, device_id, device_type, error_type, message, details } = body;

    if (!message) {
      return error('缺少 message 参数');
    }

    const ip = req.headers.get('x-forwarded-for') || req.headers.get('x-real-ip') || '';

    const detailText = [
      `错误类型: ${error_type || 'unknown'}`,
      `错误消息: ${message}`,
      details ? `详细信息: ${details}` : '',
      device_id ? `设备码: ${device_id}` : '',
      device_type ? `设备类型: ${device_type}` : '',
    ].filter(Boolean).join('\n');

    await addLog(code || 'N/A', 'error', {
      device_id: device_id || null,
      device_type: device_type || null,
      ip,
      detail: detailText,
    });

    return success({ reported: true }, '错误已上报');
  } catch (err) {
    console.error('Report error:', err);
    return error('上报失败');
  }
}
