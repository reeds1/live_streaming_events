CREATE DATABASE IF NOT EXISTS event_system DEFAULT CHARACTER SET utf8mb4;

USE event_system;

-- Table to log coupon grab events during live streaming
CREATE TABLE coupon_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    success BOOLEAN NOT NULL,
    reason VARCHAR(100),
    remaining_stock INT,
    timestamp DOUBLE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table to log like events during live streaming
CREATE TABLE like_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    is_top_like BOOLEAN NOT NULL,
    timestamp DOUBLE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table to maintain user coupon grab statistics
CREATE TABLE user_coupon_stats (
    user_id VARCHAR(100) PRIMARY KEY,
    total_attempts INT DEFAULT 0,
    successful_grabs INT DEFAULT 0,
    failed_grabs INT DEFAULT 0,
    last_attempt_time DOUBLE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table to store coupon inventory configuration
CREATE TABLE coupon_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    coupon_type VARCHAR(50) NOT NULL UNIQUE,
    total_stock INT NOT NULL,
    remaining_stock INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Initialize default coupon stock
INSERT INTO coupon_config (coupon_type, total_stock, remaining_stock)
VALUES ('default', 90000, 90000);