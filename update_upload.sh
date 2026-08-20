#!/bin/bash
# 修复上传安装包失败问题
# 原因：Next.js Route Handler 的 req.formData() 有默认大小限制（约1MB），DMG 文件约 46MB 远超限制
# 修复：改用 ReadableStream 流式读取 body + 手动解析 multipart/form-data，绕过 formData() 限制
set -e

ADMIN_DIR="/opt/codex-admin"

echo "[1/3] 更新上传接口（流式读取，绕过 formData 大小限制）..."
mkdir -p "$ADMIN_DIR/app/api/versions/upload"
cat > "$ADMIN_DIR/app/api/versions/upload/route.ts" << 'ROUTEEOF'
import { NextRequest } from 'next/server';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';
import fs from 'fs';
import path from 'path';

export const maxDuration = 300;
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

interface MultipartPart {
  name: string;
  filename?: string;
  data: Buffer;
}

function parseMultipart(buffer: Buffer, boundary: string): MultipartPart[] {
  const parts: MultipartPart[] = [];
  const boundaryBuf = Buffer.from('--' + boundary);

  let pos = 0;
  while (true) {
    const bStart = buffer.indexOf(boundaryBuf, pos);
    if (bStart === -1) break;

    const partStart = bStart + boundaryBuf.length;
    const dataStart = partStart + 2;

    const nextBoundary = buffer.indexOf(boundaryBuf, dataStart);
    if (nextBoundary === -1) break;

    const partData = buffer.slice(dataStart, nextBoundary - 2);
    const headerEnd = partData.indexOf('\r\n\r\n');
    if (headerEnd === -1) {
      pos = nextBoundary;
      continue;
    }

    const headersStr = partData.slice(0, headerEnd).toString('utf-8');
    const content = partData.slice(headerEnd + 4);

    const nameMatch = headersStr.match(/name="([^"]+)"/);
    const filenameMatch = headersStr.match(/filename="([^"]*)"/);

    if (nameMatch) {
      parts.push({
        name: nameMatch[1],
        filename: filenameMatch ? filenameMatch[1] : undefined,
        data: content,
      });
    }

    pos = nextBoundary;
  }

  return parts;
}

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const contentType = req.headers.get('content-type') || '';
    if (!contentType.includes('multipart/form-data')) {
      return error('请求格式错误，需要 multipart/form-data');
    }

    const boundaryMatch = contentType.match(/boundary=(.+)/);
    if (!boundaryMatch) {
      return error('无法解析表单边界');
    }
    const boundary = boundaryMatch[1].trim().replace(/^"|"$/g, '');

    const reader = req.body?.getReader();
    if (!reader) {
      return error('请求体为空');
    }

    const chunks: Uint8Array[] = [];
    let totalSize = 0;
    const MAX_SIZE = 200 * 1024 * 1024;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      totalSize += value.length;
      if (totalSize > MAX_SIZE) {
        return error('文件大小不能超过 200MB');
      }
    }

    const bodyBuffer = Buffer.concat(chunks);
    const parts = parseMultipart(bodyBuffer, boundary);
    const filePart = parts.find((p) => p.filename);

    if (!filePart || !filePart.filename) {
      return error('未找到上传文件');
    }

    const uploadDir = path.join(process.cwd(), 'public', 'downloads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }

    const fileName = filePart.filename.replace(/[^a-zA-Z0-9._\-\u4e00-\u9fa5]/g, '_');
    const filePath = path.join(uploadDir, fileName);
    fs.writeFileSync(filePath, filePart.data);

    const downloadUrl = `/downloads/${fileName}`;
    return success({ url: downloadUrl, filename: fileName, size: filePart.data.length }, '上传成功');
  } catch (err) {
    console.error('Upload error:', err);
    const errMsg = err instanceof Error ? err.message : String(err);
    return error(`上传失败: ${errMsg}`);
  }
}
ROUTEEOF

echo "[2/3] 重新构建..."
cd "$ADMIN_DIR"
npm run build 2>&1 | tail -5

echo "[3/3] 重启服务..."
pm2 restart codex-admin
sleep 2

echo ""
echo "=== 修复完成 ==="
echo "上传接口已改为流式读取，绕过 formData() 大小限制"
echo "现在可以上传大文件（DMG/ZIP/EXE）了"
