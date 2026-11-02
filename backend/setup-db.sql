-- =============================================================================
-- SocialApp Database & User Setup Script for MariaDB / MySQL
-- =============================================================================

CREATE DATABASE IF NOT EXISTS socialapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'socialapp'@'localhost' IDENTIFIED BY 'socialapp';
CREATE USER IF NOT EXISTS 'socialapp'@'%' IDENTIFIED BY 'socialapp';

GRANT ALL PRIVILEGES ON socialapp.* TO 'socialapp'@'localhost';
GRANT ALL PRIVILEGES ON socialapp.* TO 'socialapp'@'%';

FLUSH PRIVILEGES;
