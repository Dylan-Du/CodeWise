import { NextRequest } from 'next/server';
import pool, { addLog } from '@/lib/db';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';

/**
 * PUT /api/codes/[id]
 * 后台编辑激活码（仅备注可编辑）
 * Body: { remark }
 * 需要 Authorization header
 */
export async function PUT(
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

    const body = await req.json();
    const { remark } = body;

    const [rows]: any = await pool.query(
      'SELECT * FROM activation_codes WHERE id = ?',
      [id]
    );

    if (rows.length === 0) {
      return error('激活码不存在');
    }

    await pool.query(
      'UPDATE activation_codes SET remark = ? WHERE id = ?',
      [remark ?? '', id]
    );

    await addLog(rows[0].code, 'edit', {
      detail: `修改备注为: ${remark ?? ''}`,
    });

    return success(null, '修改成功');
  } catch (err) {
    console.error('PUT /api/codes/[id] error:', err);
    return error('修改失败');
  }
}

/**
 * DELETE /api/codes/[id]
 * 后台删除激活码
 * 需要 Authorization header
 */
export async function DELETE(
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

    await pool.query('DELETE FROM activation_codes WHERE id = ?', [id]);

    await addLog(record.code, 'delete', {
      detail: `删除激活码，原状态: ${record.status}`,
    });

    return success(null, '删除成功');
  } catch (err) {
    console.error('DELETE /api/codes/[id] error:', err);
    return error('删除失败');
  }
}
