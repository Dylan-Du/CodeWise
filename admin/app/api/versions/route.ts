import { NextRequest } from 'next/server';
import pool, { addLog } from '@/lib/db';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';

/**
 * GET /api/versions
 * 后台获取版本列表
 */
export async function GET(req: NextRequest) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const { searchParams } = new URL(req.url);
    const platform = searchParams.get('platform') || '';

    let where = 'WHERE 1=1';
    const params: unknown[] = [];
    if (platform) {
      where += ' AND platform = ?';
      params.push(platform);
    }

    const [rows]: any = await pool.query(
      `SELECT * FROM app_versions ${where} ORDER BY id DESC`,
      params
    );

    return success({ list: rows });
  } catch (err) {
    console.error('GET /api/versions error:', err);
    return error('获取版本列表失败');
  }
}

/**
 * POST /api/versions
 * 创建新版本
 */
export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const body = await req.json();
    const { version, platform, download_url, release_notes, force_update } = body;

    if (!version || !platform || !download_url) {
      return error('缺少必要字段: version, platform, download_url');
    }

    // 如果设为最新，先取消同平台其他版本的 is_latest
    if (body.is_latest) {
      await pool.query(
        'UPDATE app_versions SET is_latest = 0 WHERE platform = ?',
        [platform]
      );
    }

    const [result]: any = await pool.query(
      `INSERT INTO app_versions (version, platform, download_url, release_notes, force_update, is_latest)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [
        version,
        platform,
        download_url,
        release_notes || '',
        force_update ? 1 : 0,
        body.is_latest ? 1 : 0,
      ]
    );

    return success({ id: result.insertId }, '版本创建成功');
  } catch (err) {
    console.error('POST /api/versions error:', err);
    return error('创建版本失败');
  }
}
