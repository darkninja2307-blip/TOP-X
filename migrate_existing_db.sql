-- Run ONCE on a database created with the previous schema.sql (+ the previous migrate script).
-- Nothing is deleted: old columns stay, they just stop being used.
USE showroom;

CREATE TABLE IF NOT EXISTS users(
 id INT AUTO_INCREMENT PRIMARY KEY, discord_id VARCHAR(25) UNIQUE NOT NULL, username VARCHAR(80) NOT NULL,
 display_name VARCHAR(80), avatar VARCHAR(80), is_admin TINYINT(1) NOT NULL DEFAULT 0,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_login TIMESTAMP NULL);
CREATE TABLE IF NOT EXISTS login_log(
 id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, ip VARCHAR(64), user_agent VARCHAR(255),
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);

ALTER TABLE vehicles
 MODIFY category VARCHAR(20) NOT NULL,
 MODIFY brand VARCHAR(60) NULL DEFAULT NULL,
 MODIFY top_speed INT NOT NULL DEFAULT 0,
 MODIFY acceleration DECIMAL(4,1) NOT NULL DEFAULT 0,
 MODIFY braking TINYINT NOT NULL DEFAULT 0,
 MODIFY handling TINYINT NOT NULL DEFAULT 0,
 MODIFY horsepower INT NOT NULL DEFAULT 0,
 MODIFY drivetrain VARCHAR(10) NULL DEFAULT NULL,
 ADD COLUMN upgrade TINYINT(1) NOT NULL DEFAULT 0,
 ADD COLUMN status VARCHAR(10) NOT NULL DEFAULT 'Available';
UPDATE vehicles SET category='Bike' WHERE category='Bikes';
UPDATE vehicles SET category='Sedan' WHERE category='Sedans';
UPDATE vehicles SET category='Supercar' WHERE category='Supercars';
UPDATE vehicles SET seller=previous_owner WHERE (seller IS NULL OR seller='') AND previous_owner<>'';

ALTER TABLE bookings ADD COLUMN user_id INT NULL, ADD COLUMN discord_id VARCHAR(25);

ALTER TABLE sales_log
 CHANGE dealer buy_dealer VARCHAR(80),
 ADD COLUMN model_type VARCHAR(20), ADD COLUMN upgrade TINYINT(1) DEFAULT 0,
 ADD COLUMN sell_dealer VARCHAR(80), ADD COLUMN logged_by VARCHAR(80);
