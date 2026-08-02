/**
 * 激活码生成器
 * 格式: XXXX-XXXX-XXXX-XXXX (16位，字母数字混合)
 * 排除易混淆字符: 0, O, 1, I, l
 * 大写字母 + 数字
 */

// 排除 0, O, 1, I, l
const CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
const SEGMENT_LENGTH = 4;
const SEGMENT_COUNT = 4;

function randomChar(): string {
  const index = Math.floor(Math.random() * CHARS.length);
  return CHARS[index];
}

function generateSegment(): string {
  let segment = '';
  for (let i = 0; i < SEGMENT_LENGTH; i++) {
    segment += randomChar();
  }
  return segment;
}

/**
 * 生成单个激活码
 */
export function generateCode(): string {
  const segments: string[] = [];
  for (let i = 0; i < SEGMENT_COUNT; i++) {
    segments.push(generateSegment());
  }
  return segments.join('-');
}

/**
 * 批量生成激活码（自动去重）
 */
export function generateCodes(count: number): string[] {
  const set = new Set<string>();
  while (set.size < count) {
    set.add(generateCode());
  }
  return Array.from(set);
}
