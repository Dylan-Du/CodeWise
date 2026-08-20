import { NextRequest } from 'next/server';
import { success, error } from '@/lib/response';
import { checkAuth, unauthorized } from '@/lib/auth';
import fs from 'fs';
import path from 'path';

// 上传大文件需要更长的超时时间（5分钟）
export const maxDuration = 300;
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

interface MultipartPart {
  name: string;
  filename?: string;
  data: Buffer;
}

/**
 * 手动解析 multipart/form-data，绕过 Next.js Route Handler 的 formData() 大小限制
 * 使用 ReadableStream 流式读取 body，不会触发 body size limit
 */
function parseMultipart(buffer: Buffer, boundary: string): MultipartPart[] {
  const parts: MultipartPart[] = [];
  const boundaryBuf = Buffer.from('--' + boundary);

  let pos = 0;
  while (true) {
    const bStart = buffer.indexOf(boundaryBuf, pos);
    if (bStart === -1) break;

    const partStart = bStart + boundaryBuf.length;
    // 跳过 boundary 后的 \r\n
    const dataStart = partStart + 2;

    const nextBoundary = buffer.indexOf(boundaryBuf, dataStart);
    if (nextBoundary === -1) break;

    // part 数据（去掉末尾 \r\n）
    const partData = buffer.slice(dataStart, nextBoundary - 2);

    // 分离 headers 和 content
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

/**
 * POST /api/versions/upload
 * 上传安装包文件，返回下载地址
 * 使用流式读取 + 手动 multipart 解析，支持大文件上传
 */
export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return unauthorized();
  }

  try {
    const contentType = req.headers.get('content-type') || '';
    if (!contentType.includes('multipart/form-data')) {
      return error('请求格式错误，需要 multipart/form-data');
    }

    // 提取 boundary
    const boundaryMatch = contentType.match(/boundary=(.+)/);
    if (!boundaryMatch) {
      return error('无法解析表单边界');
    }
    const boundary = boundaryMatch[1].trim().replace(/^"|"$/g, '');

    // 流式读取 body（绕过 formData() 的大小限制）
    const reader = req.body?.getReader();
    if (!reader) {
      return error('请求体为空');
    }

    const chunks: Uint8Array[] = [];
    let totalSize = 0;
    const MAX_SIZE = 200 * 1024 * 1024; // 200MB

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

    // 解析 multipart form data
    const parts = parseMultipart(bodyBuffer, boundary);
    const filePart = parts.find((p) => p.filename);

    if (!filePart || !filePart.filename) {
      return error('未找到上传文件');
    }

    // 保存文件
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
