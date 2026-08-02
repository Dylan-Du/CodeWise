import { NextRequest } from 'next/server';
import pool, { addLog } from '@/lib/db';
import { success, error } from '@/lib/response';

/**
 * POST /api/activation/bind
 * 桌面应用绑定激活码到设备
 * Body: { code, device_id, device_type }
 * 此接口公开，无需鉴权
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { code, device_id, device_type } = body;

    if (!code || !device_id || !device_type) {
      return error('缺少必要参数: code, device_id, device_type');
    }

    if (!['win', 'mac'].includes(device_type)) {
      return error('device_type 必须为 win 或 mac');
    }

    const ip = req.headers.get('x-forwarded-for') || req.headers.get('x-real-ip') || '';

    const [rows]: any = await pool.query(
      'SELECT * FROM activation_codes WHERE code = ?',
      [code]
    );

    if (rows.length === 0) {
      await addLog(code, 'bind', { device_id, device_type, ip, detail: '激活码不存在' });
      return error('激活码不存在');
    }

    const record = rows[0];

    if (record.status === 'disabled') {
      await addLog(code, 'bind', { device_id, device_type, ip, detail: '激活码已禁用' });
      return error('激活码已被禁用');
    }

    // 已绑定到当前设备
    if (record.status === 'bound' && record.device_id === device_id) {
      // 检查是否过期
      if (record.expires_at) {
        const expiresAt = new Date(record.expires_at);
        if (expiresAt.getTime() < Date.now()) {
          await addLog(code, 'bind', { device_id, device_type, ip, detail: '激活码已过期' });
          return error('激活码已过期');
        }
      }
      await addLog(code, 'bind', { device_id, device_type, ip, detail: '设备已绑定，重复绑定' });
      return success({
        bound: true,
        message: '该设备已绑定此激活码',
        type: record.type,
        expires_at: record.expires_at,
      }, '绑定成功');
    }

    // 已绑定到其他设备
    if (record.status === 'bound' && record.device_id !== device_id) {
      await addLog(code, 'bind', { device_id, device_type, ip, detail: '已绑定到其他设备' });
      return error('激活码已绑定到其他设备');
    }

    // status === 'unused'，执行绑定
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    const nowStr = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    let expiresAt: string | null = null;

    if (record.type === 'day' && record.days > 0) {
      const exp = new Date(now.getTime() + record.days * 24 * 60 * 60 * 1000);
      expiresAt = `${exp.getFullYear()}-${pad(exp.getMonth()+1)}-${pad(exp.getDate())} ${pad(exp.getHours())}:${pad(exp.getMinutes())}:${pad(exp.getSeconds())}`;
    }

    await pool.query(
      `UPDATE activation_codes
       SET status = 'bound', device_type = ?, device_id = ?, bound_at = ?, expires_at = ?
       WHERE id = ?`,
      [device_type, device_id, nowStr, expiresAt, record.id]
    );

    await addLog(code, 'bind', {
      device_id,
      device_type,
      ip,
      detail: `绑定成功，类型: ${record.type}${record.type === 'day' ? `, 天数: ${record.days}` : ''}`,
    });

    return success(
      {
        bound: true,
        message: '绑定成功',
        type: record.type,
        expires_at: expiresAt,
      },
      '绑定成功'
    );
  } catch (err) {
    console.error('Bind error:', err);
    return error('服务器内部错误');
  }
}
