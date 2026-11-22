-- ============================================================
-- SmartMart Analytics - Dimensional Data Warehouse Schema
-- Architecture: Star Schema
-- Database: smartmart_dw
-- ============================================================

CREATE DATABASE IF NOT EXISTS `smartmart_dw`
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `smartmart_dw`;

-- Disable foreign key checks for clean drop order during re-runs
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `Fact_Sales`;
DROP TABLE IF EXISTS `Dim_Product`;
DROP TABLE IF EXISTS `Dim_Customer`;
DROP TABLE IF EXISTS `Dim_Date`;
DROP TABLE IF EXISTS `Dim_Country`;
SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- 1. Dim_Product
-- Stores unique products referenced by StockCode.
-- ------------------------------------------------------------
CREATE TABLE `Dim_Product` (
    `Product_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `StockCode` VARCHAR(50) NOT NULL UNIQUE,
    `Description` VARCHAR(255) NULL,
    INDEX `idx_product_stockcode` (`StockCode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 2. Dim_Customer
-- Stores unique customer identifiers.
-- Special record Customer_ID=1 (CustomerCode='UNKNOWN') handles missing identifiers.
-- ------------------------------------------------------------
CREATE TABLE `Dim_Customer` (
    `Customer_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `CustomerCode` VARCHAR(50) NOT NULL UNIQUE,
    INDEX `idx_customer_code` (`CustomerCode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Pre-seed the Unknown customer member for missing customer codes
INSERT INTO `Dim_Customer` (`Customer_ID`, `CustomerCode`)
VALUES (1, 'UNKNOWN')
ON DUPLICATE KEY UPDATE `CustomerCode`='UNKNOWN';

-- ------------------------------------------------------------
-- 3. Dim_Date
-- Calendar dimension table with Date_ID in YYYYMMDD integer format.
-- Supports OLAP roll-up / drill-down (Day -> Month -> Quarter -> Year).
-- ------------------------------------------------------------
CREATE TABLE `Dim_Date` (
    `Date_ID` INT PRIMARY KEY,
    `FullDate` DATE NOT NULL,
    `DayNumber` TINYINT NOT NULL,
    `MonthNumber` TINYINT NOT NULL,
    `MonthName` VARCHAR(20) NOT NULL,
    `QuarterNumber` TINYINT NOT NULL,
    `YearNumber` SMALLINT NOT NULL,
    INDEX `idx_date_fulldate` (`FullDate`),
    INDEX `idx_date_year_month` (`YearNumber`, `MonthNumber`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 4. Dim_Country
-- Stores unique country names for geographic slicing and dicing.
-- ------------------------------------------------------------
CREATE TABLE `Dim_Country` (
    `Country_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `CountryName` VARCHAR(100) NOT NULL UNIQUE,
    INDEX `idx_country_name` (`CountryName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 5. Fact_Sales
-- Central Fact table.
-- Grain: One product line within one invoice.
-- Additive measures: Quantity, UnitPrice, TotalAmount.
-- ------------------------------------------------------------
CREATE TABLE `Fact_Sales` (
    `Sales_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `InvoiceNo` VARCHAR(50) NOT NULL,
    `Product_ID` INT NOT NULL,
    `Customer_ID` INT NOT NULL,
    `Date_ID` INT NOT NULL,
    `Country_ID` INT NOT NULL,
    `Quantity` INT NOT NULL,
    `UnitPrice` DECIMAL(10, 2) NOT NULL,
    `TotalAmount` DECIMAL(12, 2) NOT NULL,
    
    -- Foreign Key Constraints
    CONSTRAINT `fk_fact_product` FOREIGN KEY (`Product_ID`) 
        REFERENCES `Dim_Product` (`Product_ID`) 
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_fact_customer` FOREIGN KEY (`Customer_ID`) 
        REFERENCES `Dim_Customer` (`Customer_ID`) 
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_fact_date` FOREIGN KEY (`Date_ID`) 
        REFERENCES `Dim_Date` (`Date_ID`) 
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_fact_country` FOREIGN KEY (`Country_ID`) 
        REFERENCES `Dim_Country` (`Country_ID`) 
        ON DELETE RESTRICT ON UPDATE CASCADE,

    -- Dimensional Performance Indexes
    INDEX `idx_fact_invoiceno` (`InvoiceNo`),
    INDEX `idx_fact_product` (`Product_ID`),
    INDEX `idx_fact_customer` (`Customer_ID`),
    INDEX `idx_fact_date` (`Date_ID`),
    INDEX `idx_fact_country` (`Country_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
