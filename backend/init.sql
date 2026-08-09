-- 课堂签到助手 数据库初始化
CREATE DATABASE IF NOT EXISTS chaoxing DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE chaoxing;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nickname VARCHAR(64) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    password_hash VARCHAR(256) COMMENT '方案1: 加密存密码',
    cookie_manual TEXT COMMENT '方案2: 手动抓的Cookie',
    cookie_expire_at DATETIME COMMENT 'Cookie过期时间',
    cookie_source VARCHAR(10) DEFAULT 'auto' COMMENT 'auto/manual',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 课程表
CREATE TABLE IF NOT EXISTS courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id VARCHAR(64) NOT NULL UNIQUE COMMENT '学习通真实courseId',
    course_name VARCHAR(128),
    creator_id INT NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 课程成员表
CREATE TABLE IF NOT EXISTS course_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_course (user_id, course_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 签到日志表
CREATE TABLE IF NOT EXISTS sign_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    active_id VARCHAR(64),
    enc VARCHAR(128),
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'success/fail/expired/pending',
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
