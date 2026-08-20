import mysql from 'mysql2/promise';

// 读取环境变量，默认使用本机 MySQL 配置
const DB_HOST = process.env.DB_HOST || '127.0.0.1';
const DB_PORT = parseInt(process.env.DB_PORT || '3306');
const DB_USER = process.env.DB_USER || 'root';
const DB_PASSWORD = process.env.DB_PASSWORD || '';
const DB_NAME = process.env.DB_NAME || 'codex_admin';

// 日志保留天数（超期自动清理）
const LOG_RETENTION_DAYS = 30;

// 创建 MySQL 连接池
const pool = mysql.createPool({
  host: DB_HOST,
  port: DB_PORT,
  user: DB_USER,
  password: DB_PASSWORD,
  database: DB_NAME,
  waitForConnections: true,
  connectionLimit: 20,
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
    await conn.execute(`
      CREATE TABLE IF NOT EXISTS app_versions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        version VARCHAR(50) NOT NULL,
        platform VARCHAR(20) NOT NULL DEFAULT 'mac',
        download_url VARCHAR(500) NOT NULL,
        release_notes TEXT,
        force_update TINYINT DEFAULT 0,
        is_latest TINYINT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    console.log('数据库表初始化完成');
  } finally {
    conn.release();
  }

  // 索引迁移（表已存在时 CREATE TABLE IF NOT EXISTS 不会执行，需单独补建索引）
  await ensureIndex('activation_logs', 'idx_logs_created_at', 'created_at');
  await ensureIndex('activation_logs', 'idx_logs_action', 'action');
  await ensureIndex('activation_logs', 'idx_logs_code', 'code');
  await ensureIndex('activation_codes', 'idx_codes_status', 'status');
  await ensureIndex('activation_codes', 'idx_codes_type', 'type');
}

// 检查并创建索引（MySQL 不支持 CREATE INDEX IF NOT EXISTS，需查 information_schema）
async function ensureIndex(table: string, indexName: string, columns: string) {
  try {
    const [rows]: any = await pool.query(
      'SELECT COUNT(*) AS cnt FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = ? AND index_name = ?',
      [table, indexName]
    );
    if ((rows[0]?.cnt || 0) === 0) {
      await pool.query(`CREATE INDEX ${indexName} ON ${table} (${columns})`);
      console.log(`索引已创建: ${table}.${indexName}`);
    }
  } catch (err) {
    console.error(`创建索引失败 ${table}.${indexName}:`, err);
  }
}

// 清理过期日志（分批删除，避免长时间锁表影响线上查询）
export async function cleanupOldLogs(
  retentionDays: number = LOG_RETENTION_DAYS
): Promise<number> {
  let total = 0;
  try {
    for (;;) {
      const [result]: any = await pool.query(
        'DELETE FROM activation_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL ? DAY) ORDER BY id LIMIT 5000',
        [retentionDays]
      );
      const n = result.affectedRows || 0;
      total += n;
      if (n < 5000) break;
      // 每批之间短暂停顿，把连接让给线上请求
      await new Promise((r) => setTimeout(r, 200));
    }
  } catch (err) {
    console.error('清理过期日志失败:', err);
  }
  return total;
}

// 导出兼容 pool 接口
const dbPool = {
  async query(sql: string, params?: any[]): Promise<[any[], any]> {
    const [rows, fields] = await pool.query(sql, params || []);
    return [rows as any[], fields as any];
  },
  raw: pool,
};

// 初始化数据库 + 启动时清理一次过期日志
initDB()
  .then(async () => {
    const n = await cleanupOldLogs();
    if (n > 0) console.log(`启动清理完成，删除过期日志 ${n} 条`);
  })
  .catch((err) => {
    console.error('数据库初始化失败:', err);
  });

// 每日定时清理过期日志（用 globalThis 标记防止 dev 模式热更新重复启动）
const g = globalThis as any;
if (!g.__logCleanupStarted__) {
  g.__logCleanupStarted__ = true;
  setInterval(() => {
    cleanupOldLogs().then((n) => {
      if (n > 0) console.log(`定时清理完成，删除过期日志 ${n} 条`);
    });
  }, 24 * 60 * 60 * 1000);
}

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

/**
 * 批量插入操作日志（单条 multi-VALUES，避免逐条插入的多次数据库往返）
 */
export async function addLogs(
  logs: Array<{
    code: string;
    action: string;
    data?: {
      device_id?: string | null;
      device_type?: string | null;
      ip?: string | null;
      detail?: string | null;
    } | null;
  }>
): Promise<void> {
  try {
    if (!logs || logs.length === 0) return;
    const values = logs.map(() => '(?, ?, ?, ?, ?, ?)').join(', ');
    const params: unknown[] = [];
    for (const log of logs) {
      params.push(
        log.code,
        log.action,
        log.data?.device_id ?? null,
        log.data?.device_type ?? null,
        log.data?.ip ?? null,
        log.data?.detail ?? null
      );
    }
    await pool.query(
      'INSERT INTO activation_logs (code, action, device_id, device_type, ip, detail) VALUES ' +
        values,
      params
    );
  } catch (err) {
    console.error('Failed to add logs:', err);
  }
}
