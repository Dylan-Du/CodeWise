import { NextRequest } from 'next/server';
import pool, { addLog } from '@/lib/db';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';

/**
 * POST /api/codes/[id]/unbind
 * 后台解绑激活码
 * 需要 Authorization header
 */
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const id = parseInt(params.id, 10);
    if (isNaN(id)) {
      return error('无效的 ID');
    }

    const [rows]: any = await pool.query(
      'SELECT * FROM activation_codes WHERE id = ?',
      [id]
    );

    if (rows.length === 0) {
      return error('激活码不存在');
    }

    const record = rows[0];

    if (record.status !== 'bound') {
      return error('该激活码未绑定，无需解绑');
    }

    await pool.query(
      `UPDATE activation_codes
       SET status = 'unused', device_type = NULL, device_id = NULL,
           bound_at = NULL, expires_at = NULL
       WHERE id = ?`,
      [id]
    );

    await addLog(record.code, 'unbind', {
      device_id: record.device_id,
      device_type: record.device_type,
      detail: `后台解绑，原设备: ${record.device_id || '无'}`,
    });

    return success(null, '解绑成功');
  } catch (err) {
    console.error('Unbind error:', err);
    return error('解绑失败');
  }
}
