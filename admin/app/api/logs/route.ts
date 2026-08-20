import { NextRequest } from 'next/server';
import pool from '@/lib/db';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';

/**
 * GET /api/logs
 * 后台获取日志列表（分页 + 筛选）
 * Query: page, pageSize, action, keyword, startDate, endDate
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
    const action = searchParams.get('action') || '';
    const keyword = searchParams.get('keyword') || '';
    const startDate = searchParams.get('startDate') || '';
    const endDate = searchParams.get('endDate') || '';

    let where = 'WHERE 1=1';
    const params: unknown[] = [];

    if (action) {
      where += ' AND action = ?';
      params.push(action);
    }
    if (keyword) {
      where += ' AND (code LIKE ? OR detail LIKE ? OR device_id LIKE ?)';
      params.push(`%${keyword}%`, `%${keyword}%`, `%${keyword}%`);
    }
    if (startDate) {
      where += ' AND created_at >= ?';
      params.push(startDate);
    }
    if (endDate) {
      where += ' AND created_at <= ?';
      params.push(endDate + ' 23:59:59');
    }

    // 获取总数
    const [countRows]: any = await pool.query(
      `SELECT COUNT(*) as total FROM activation_logs ${where}`,
      params
    );
    const total = countRows[0].total;

    // 获取分页数据
    const offset = (page - 1) * pageSize;
    const [rows]: any = await pool.query(
      `SELECT * FROM activation_logs ${where} ORDER BY id DESC LIMIT ${pageSize} OFFSET ${offset}`,
      params
    );

    return success({
      list: rows,
      total,
      page,
      pageSize,
    });
  } catch (err) {
    console.error('GET /api/logs error:', err);
    return error('获取日志列表失败');
  }
}
