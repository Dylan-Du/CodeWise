import { NextRequest } from 'next/server';
import pool from '@/lib/db';
import { success, error } from '@/lib/response';

/**
 * GET /api/versions/check
 * 应用端检查更新（公开接口，无需鉴权）
 * Query: platform=mac|win, current_version=1.0.0
 */
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const platform = searchParams.get('platform') || 'mac';
    const currentVersion = searchParams.get('current_version') || '0.0.0';

    const [rows]: any = await pool.query(
      `SELECT * FROM app_versions WHERE platform = ? AND is_latest = 1 LIMIT 1`,
      [platform]
    );

    if (rows.length === 0) {
      return success({ has_update: false });
    }

    const latest = rows[0];

    // 简单版本比较
    const compareVersions = (a: string, b: string): number => {
      const pa = a.split('.').map(Number);
      const pb = b.split('.').map(Number);
      for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
        const va = pa[i] || 0;
        const vb = pb[i] || 0;
        if (va > vb) return 1;
        if (va < vb) return -1;
      }
      return 0;
    };

    const hasUpdate = compareVersions(latest.version, currentVersion) > 0;

    return success({
      has_update: hasUpdate,
      version: latest.version,
      download_url: latest.download_url,
      release_notes: latest.release_notes || '',
      force_update: !!latest.force_update,
    });
  } catch (err) {
    console.error('GET /api/versions/check error:', err);
    return error('检查更新失败');
  }
}
