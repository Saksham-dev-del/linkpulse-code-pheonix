-- LinkPulse MySQL 8 schema (reference deployment schema).
CREATE DATABASE IF NOT EXISTS linkpulse CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE linkpulse;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('user','admin') NOT NULL DEFAULT 'user',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  owner_id BIGINT NULL,
  start_date DATETIME NULL,
  end_date DATETIME NULL,
  status ENUM('active','paused','completed') NOT NULL DEFAULT 'active',
  FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS links (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  short_code VARCHAR(32) NOT NULL UNIQUE,
  destination_url TEXT NOT NULL,
  owner_id BIGINT NULL,
  campaign_id BIGINT NULL,
  campaign VARCHAR(120) NOT NULL DEFAULT 'General',
  tags VARCHAR(500) NOT NULL DEFAULT '',
  password_hash VARCHAR(255) NULL,
  expires_at DATETIME NULL,
  click_cap BIGINT NULL,
  total_clicks BIGINT NOT NULL DEFAULT 0,
  status ENUM('active','disabled') NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_links_status_created (status, created_at),
  INDEX idx_links_campaign (campaign),
  FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS redirect_rules (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  link_id BIGINT NOT NULL,
  type ENUM('expiry','click_cap','password','device') NOT NULL,
  value VARCHAR(500) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE,
  INDEX idx_rules_link_priority (link_id, priority)
);

CREATE TABLE IF NOT EXISTS click_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  link_id BIGINT NOT NULL,
  clicked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  referrer VARCHAR(500) NOT NULL DEFAULT 'Direct',
  device VARCHAR(40) NOT NULL DEFAULT 'Unknown',
  browser VARCHAR(80) NOT NULL DEFAULT 'Unknown',
  country VARCHAR(80) NULL,
  is_bot BOOLEAN NOT NULL DEFAULT FALSE,
  visitor_id VARCHAR(64) NULL,
  FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE,
  INDEX idx_click_link_time (link_id, clicked_at),
  INDEX idx_click_time (clicked_at)
);

CREATE TABLE IF NOT EXISTS tags (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,
  owner_id BIGINT NULL,
  UNIQUE KEY uq_tag_owner_name (owner_id, name),
  FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS link_tags (
  link_id BIGINT NOT NULL,
  tag_id BIGINT NOT NULL,
  PRIMARY KEY (link_id, tag_id),
  FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS qr_codes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  link_id BIGINT NOT NULL,
  image_path VARCHAR(500) NOT NULL,
  scan_count BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE
);
