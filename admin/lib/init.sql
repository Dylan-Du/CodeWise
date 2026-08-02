-- ============================================
-- 激活码管理系统 - 数据库初始化 SQL
-- ============================================

CREATE DATABASE IF NOT EXISTS activation_admin
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE activation_admin;

-- --------------------------------------------
-- 激活码表
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS activation_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(32) UNIQUE NOT NULL COMMENT '激活码',
  type ENUM('day', 'permanent') NOT NULL COMMENT '按天/永久',
  days INT DEFAULT 0 COMMENT '按天类型的有效天数',
  status ENUM('unused', 'bound', 'disabled') DEFAULT 'unused' COMMENT '状态',
  device_type ENUM('win', 'mac') NULL COMMENT '绑定设备类型',
  device_id VARCHAR(128) NULL COMMENT '绑定设备码',
  bound_at DATETIME NULL COMMENT '绑定时间',
  expires_at DATETIME NULL COMMENT '过期时间(按天类型)',
  remark VARCHAR(255) DEFAULT '' COMMENT '备注',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_status (status),
  INDEX idx_type (type),
  INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 日志表
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS activation_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(32) NOT NULL COMMENT '激活码',
  action VARCHAR(32) NOT NULL COMMENT 'bind/unbind/verify/create/delete/edit',
  device_id VARCHAR(128) NULL COMMENT '设备码',
  device_type ENUM('win', 'mac') NULL,
  ip VARCHAR(64) NULL,
  detail TEXT NULL COMMENT '详情',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_code (code),
  INDEX idx_action (action),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
