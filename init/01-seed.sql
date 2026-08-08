-- ============================================================
-- yappy_profile
-- ============================================================
CREATE DATABASE IF NOT EXISTS yappy_profile;
USE yappy_profile;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    status ENUM('active', 'inactive', 'banned') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE user_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url VARCHAR(500),
    bio TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO users (username, email, phone, status) VALUES
    ('alice', 'alice@example.com', '+5491155551234', 'active'),
    ('bob', 'bob@example.com', '+5491155555678', 'active'),
    ('charlie', 'charlie@example.com', NULL, 'inactive');

INSERT INTO user_profiles (user_id, first_name, last_name, bio) VALUES
    (1, 'Alice', 'Garcia', 'Backend developer'),
    (2, 'Bob', 'Lopez', 'DevOps engineer'),
    (3, 'Charlie', 'Martinez', NULL);

-- ============================================================
-- yappy_payment
-- ============================================================
CREATE DATABASE IF NOT EXISTS yappy_payment;
USE yappy_payment;

CREATE TABLE merchants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    alias VARCHAR(50) NOT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    merchant_id INT NOT NULL,
    user_id INT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ARS',
    status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
    idempotency_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);

CREATE TABLE payment_methods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    type ENUM('card', 'qr', 'cvu', 'alias') NOT NULL,
    provider VARCHAR(50),
    last_four VARCHAR(4),
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO merchants (name, alias) VALUES
    ('Café del Sol', 'cafedelsol'),
    ('Librería Central', 'libreriacentral'),
    ('TechStore', 'techstore');

INSERT INTO transactions (merchant_id, user_id, amount, status, idempotency_key) VALUES
    (1, 1, 1500.00, 'completed', 'idem-001'),
    (1, 2, 3200.50, 'completed', 'idem-002'),
    (2, 1, 890.00, 'pending', 'idem-003'),
    (3, 3, 15000.00, 'failed', 'idem-004');

INSERT INTO payment_methods (user_id, type, provider, last_four, is_default) VALUES
    (1, 'card', 'visa', '1234', TRUE),
    (1, 'qr', NULL, NULL, FALSE),
    (2, 'card', 'mastercard', '5678', TRUE);

-- ============================================================
-- yappy_authentication
-- ============================================================
CREATE DATABASE IF NOT EXISTS yappy_authentication;
USE yappy_authentication;

CREATE TABLE auth_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    type ENUM('access', 'refresh') NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL
);

CREATE TABLE oauth_clients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id VARCHAR(100) NOT NULL UNIQUE,
    client_secret VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    redirect_uri VARCHAR(500),
    scopes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE mfa_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    code VARCHAR(10) NOT NULL,
    type ENUM('sms', 'email', 'totp') NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO auth_tokens (user_id, token_hash, type, expires_at) VALUES
    (1, 'abc123hash', 'access', '2026-08-09 00:00:00'),
    (1, 'def456hash', 'refresh', '2026-08-15 00:00:00'),
    (2, 'ghi789hash', 'access', '2026-08-09 00:00:00');

INSERT INTO oauth_clients (client_id, client_secret, name, redirect_uri, scopes) VALUES
    ('yappy-web', 'secret-web-123', 'Yappy Web App', 'http://localhost:3000/callback', 'read write'),
    ('yappy-mobile', 'secret-mobile-456', 'Yappy Mobile', 'yappy://callback', 'read write admin');
