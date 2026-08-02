import mysql from 'mysql2/promise';
import fs from 'fs';

// 读取环境变量，默认使用 SQLite 配置（本地开发兼容）
const DB_HOST = process.env.DB_HOST || '127.0.0.1';
const DB_PORT = parseInt(process.env.DB_PORT || '3306');
const DB_USER = process.env.DB_USER || 'root';
const DB_PASSWORD = process.env.DB_PASSWORD || '';
const DB_NAME = process.env.DB_NAME || 'codex_admin';

// 创建 MySQL 连接池
const pool = mysql.createPool({
  host: DB_HOST,
  port: DB_PORT,
  user: DB_USER,
  password: DB_PASSWORD,
  database: DB_NAME,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
});

// 自动建表
async function initDB() {
  const conn = await pool.getConnection();
  try {
    await conn.execute(`
      CREATE TABLE IF NOT EXISTS activation_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(100) UNIQUE NOT NULL,
        type VARCHAR(20) NOT NULL DEFAULT 'day',
        days INT DEFAULT 0,
        status VARCHAR(20) DEFAULT 'unused',
        device_type VARCHAR(50),
        device_id VARCHAR(255),
        bound_at DATETIME NULL,
        expires_at DATETIME NULL,
        remark VARCHAR(500) DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      )
    `);
    await conn.execute(`
      CREATE TABLE IF NOT EXISTS activation_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(100) NOT NULL,
        action VARCHAR(50) NOT NULL,
        device_id VARCHAR(255),
        device_type VARCHAR(50),
        ip VARCHAR(50),
        detail TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    console.log('数据库表初始化完成');
  } finally {
    conn.release();
  }
}

// 导出兼容 pool 接口
const dbPool = {
  async query(sql: string, params?: any[]): Promise<[any[], any]> {
    const [rows, fields] = await pool.query(sql, params || []);
    return [rows as any[], fields as any];
  },
  raw: pool,
};

// 初始化数据库
initDB().catch(err => {
  console.error('数据库初始化失败:', err);
});

export default dbPool;

/**
 * 插入操作日志
 */
export async function addLog(
  code: string,
  action: string,
  data: {
    device_id?: string | null;
    device_type?: string | null;
    ip?: string | null;
    detail?: string | null;
  } = {}
): Promise<void> {
  try {
    await pool.execute(
      'INSERT INTO activation_logs (code, action, device_id, device_type, ip, detail) VALUES (?, ?, ?, ?, ?, ?)',
      [
        code,
        action,
        data.device_id ?? null,
        data.device_type ?? null,
        data.ip ?? null,
        data.detail ?? null,
      ]
    );
  } catch (err) {
    console.error('Failed to add log:', err);
  }
}
