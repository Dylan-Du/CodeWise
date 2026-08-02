import { NextRequest } from 'next/server';
import pool, { addLog } from '@/lib/db';
import { success, error } from '@/lib/response';

/**
 * POST /api/activation/verify
 * 桌面应用校验激活码是否有效
 * Body: { code, device_id, device_type }
 * 此接口公开，无需鉴权
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { code, device_id, device_type } = body;

    if (!code || !device_id) {
      return error('缺少必要参数: code, device_id');
    }

    const [rows]: any = await pool.query(
      'SELECT * FROM activation_codes WHERE code = ?',
      [code]
    );

    if (rows.length === 0) {
      await addLog(code, 'verify', { device_id, device_type, detail: '激活码不存在' });
      return success({ valid: false, message: '激活码不存在' });
    }

    const record = rows[0];

    if (record.status === 'disabled') {
      await addLog(code, 'verify', { device_id, device_type, detail: '激活码已禁用' });
      return success({ valid: false, message: '激活码已禁用' });
    }

    if (record.status === 'unused') {
      await addLog(code, 'verify', { device_id, device_type, detail: '激活码未绑定' });
      return success({ valid: false, message: '激活码尚未绑定，请先绑定设备' });
    }

    // status === 'bound'
    if (record.device_id !== device_id) {
      await addLog(code, 'verify', { device_id, device_type, detail: '设备不匹配' });
      return success({ valid: false, message: '激活码已绑定到其他设备' });
    }

    // 检查是否过期
    if (record.expires_at) {
      const expiresAt = new Date(record.expires_at);
      if (expiresAt.getTime() < Date.now()) {
        await addLog(code, 'verify', { device_id, device_type, detail: '激活码已过期' });
        return success({ valid: false, message: '激活码已过期' });
      }
    }

    await addLog(code, 'verify', { device_id, device_type, detail: '验证通过' });
    return success({
      valid: true,
      message: '激活码有效',
      type: record.type,
      expires_at: record.expires_at,
    });
  } catch (err) {
    console.error('Verify error:', err);
    return error('服务器内部错误');
  }
}
