import { NextRequest } from 'next/server';
import pool from '@/lib/db';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';
import fs from 'fs';
import path from 'path';

/**
 * DELETE /api/versions/[id]
 * 删除版本，同时删除上传的安装包文件
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
    if (!id) {
      return error('无效的版本 ID');
    }

    // 先查出下载地址，判断是否是本地上传的文件
    const [rows]: any = await pool.query(
      'SELECT download_url FROM app_versions WHERE id = ?',
      [id]
    );

    if (rows.length > 0) {
      const downloadUrl = rows[0].download_url || '';

      // 如果是本地上传的文件（/downloads/xxx），删除磁盘文件
      if (downloadUrl.startsWith('/downloads/')) {
        const fileName = downloadUrl.replace('/downloads/', '');
        const filePath = path.join(process.cwd(), 'public', 'downloads', fileName);
        try {
          if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
          }
        } catch (e) {
          // 文件删除失败不影响数据库删除
          console.error('删除文件失败:', e);
        }
      }
    }

    // 删除数据库记录
    await pool.query('DELETE FROM app_versions WHERE id = ?', [id]);
    return success({}, '版本已删除，安装包文件已清理');
  } catch (err) {
    console.error('DELETE /api/versions error:', err);
    return error('删除版本失败');
  }
}
