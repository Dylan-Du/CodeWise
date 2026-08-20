import { NextRequest } from 'next/server';
import pool, { addLogs } from '@/lib/db';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';
import { generateCodes } from '@/lib/code-generator';

/**
 * GET /api/codes
 * 后台获取激活码列表（分页 + 筛选）
 * Query: page, pageSize, status, type, keyword
 * 需要 Authorization header
 */
export async function GET(req: NextRequest) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const { searchParams } = new URL(req.url);
    const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10));
    const pageSize = Math.max(1, Math.min(100, parseInt(searchParams.get('pageSize') || '10', 10)));
    const status = searchParams.get('status') || '';
    const type = searchParams.get('type') || '';
    const keyword = searchParams.get('keyword') || '';

    let where = 'WHERE 1=1';
    const params: unknown[] = [];

    if (status) {
      where += ' AND status = ?';
      params.push(status);
    }
    if (type) {
      where += ' AND type = ?';
      params.push(type);
    }
    if (keyword) {
      where += ' AND code LIKE ?';
      params.push(`%${keyword}%`);
    }

    // 获取总数
    const [countRows]: any = await pool.query(
      `SELECT COUNT(*) as total FROM activation_codes ${where}`,
      params
    );
    const total = countRows[0].total;

    // 获取分页数据
    const offset = (page - 1) * pageSize;
    const [rows]: any = await pool.query(
      `SELECT * FROM activation_codes ${where} ORDER BY id DESC LIMIT ${pageSize} OFFSET ${offset}`,
      params
    );

    return success({
      list: rows,
      total,
      page,
      pageSize,
    });
  } catch (err) {
    console.error('GET /api/codes error:', err);
    return error('获取列表失败');
  }
}

/**
 * POST /api/codes
 * 后台创建激活码（支持批量）
 * Body: { type, days, count, remark }
 * 需要 Authorization header
 */
export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const body = await req.json();
    const { type, days = 0, count = 1, remark = '' } = body;

    if (!type || !['day', 'permanent'].includes(type)) {
      return error('type 必须为 day 或 permanent');
    }

    if (type === 'day' && (!days || days <= 0)) {
      return error('按天类型必须指定有效天数');
    }

    const createCount = Math.max(1, Math.min(100, count));

    // 生成激活码
    const codes = generateCodes(createCount);

    // 批量插入激活码（单条 multi-VALUES，避免逐条插入的多次数据库往返）
    if (codes.length > 0) {
      const values = codes.map(() => '(?, ?, ?, ?, ?)').join(', ');
      const insertParams: unknown[] = [];
      for (const code of codes) {
        insertParams.push(code, type, type === 'day' ? days : 0, 'unused', remark);
      }
      await pool.query(
        `INSERT INTO activation_codes (code, type, days, status, remark) VALUES ${values}`,
        insertParams
      );
    }

    // 批量记录日志
    await addLogs(
      codes.map((code) => ({
        code,
        action: 'create',
        data: {
          detail: `批量创建，类型: ${type}${type === 'day' ? `, 天数: ${days}` : ''}, 数量: ${createCount}`,
        },
      }))
    );

    return success({ codes }, `成功创建 ${createCount} 个激活码`);
  } catch (err) {
    console.error('POST /api/codes error:', err);
    return error('创建激活码失败');
  }
}
