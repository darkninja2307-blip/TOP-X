
-- Discord login accounts (filled automatically on first login)
CREATE TABLE IF NOT EXISTS users(
 id INT AUTO_INCREMENT PRIMARY KEY,
 discord_id VARCHAR(25) UNIQUE NOT NULL,
 username VARCHAR(80) NOT NULL,
 display_name VARCHAR(80),
 avatar VARCHAR(80),
 is_admin TINYINT(1) NOT NULL DEFAULT 0,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 last_login TIMESTAMP NULL);

CREATE TABLE IF NOT EXISTS login_log(
 id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, ip VARCHAR(64), user_agent VARCHAR(255),
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);

-- Vehicle catalog (added by admin)
CREATE TABLE IF NOT EXISTS vehicles(
 id INT AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(80) NOT NULL,                 -- vehicle name
 category VARCHAR(20) NOT NULL,             -- model type: Sedan, SUV, Bike, Sports, Supercar, Luxury, Other
 plate_no VARCHAR(20) NOT NULL,
 upgrade TINYINT(1) NOT NULL DEFAULT 0,     -- 1 = upgraded, 0 = non-upgraded
 seller VARCHAR(80) NOT NULL,               -- car seller (old owner)
 dealer VARCHAR(80) NOT NULL,               -- dealer who bought the car   (private)
 purchase_price INT NOT NULL DEFAULT 0,     -- purchase amount             (private)
 price INT NOT NULL,                        -- listing / selling price
 description TEXT, image VARCHAR(255),
 status VARCHAR(10) NOT NULL DEFAULT 'Available',   -- Available | Sold
 available TINYINT(1) NOT NULL DEFAULT 1,           -- kept in sync with status
 featured TINYINT(1) NOT NULL DEFAULT 0,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS bookings(
 id INT AUTO_INCREMENT PRIMARY KEY, ref VARCHAR(16) UNIQUE NOT NULL, vehicle_id INT NOT NULL,
 user_id INT NULL, discord_id VARCHAR(25),
 player_name VARCHAR(60) NOT NULL, player_id VARCHAR(20) NOT NULL, discord VARCHAR(60) NOT NULL, message TEXT,
 status ENUM('Pending','Approved','Rejected','Completed') DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE);

-- Full sale log: snapshot of the car + who bought it, who sold it, and for how much
CREATE TABLE IF NOT EXISTS sales_log(
 id INT AUTO_INCREMENT PRIMARY KEY, vehicle_id INT NULL,
 vehicle_name VARCHAR(80) NOT NULL, model_type VARCHAR(20), plate_no VARCHAR(20), upgrade TINYINT(1) DEFAULT 0,
 seller VARCHAR(80),                        -- old owner
 buy_dealer VARCHAR(80),                    -- dealer who bought the car from the old owner
 purchase_price INT DEFAULT 0,
 customer VARCHAR(80) NOT NULL,             -- customer name
 sell_dealer VARCHAR(80),                   -- dealer who sold the car to the customer
 sold_amount INT DEFAULT 0,
 note VARCHAR(500), logged_by VARCHAR(80),
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL);
