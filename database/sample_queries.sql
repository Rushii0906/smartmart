-- ============================================================
-- SmartMart Analytics - Sample OLAP & Data Mining SQL Queries
-- Demonstrating Star Schema Joins, OLAP Operations, and Aggregations
-- ============================================================

USE `smartmart_dw`;

-- ------------------------------------------------------------
-- 1. Star Schema Verification: Record Counts
-- ------------------------------------------------------------
SELECT 'Dim_Product' AS TableName, COUNT(*) AS TotalRows FROM Dim_Product
UNION ALL
SELECT 'Dim_Customer', COUNT(*) FROM Dim_Customer
UNION ALL
SELECT 'Dim_Date', COUNT(*) FROM Dim_Date
UNION ALL
SELECT 'Dim_Country', COUNT(*) FROM Dim_Country
UNION ALL
SELECT 'Fact_Sales', COUNT(*) FROM Fact_Sales;

-- ------------------------------------------------------------
-- 2. Star Schema Join: Denormalized Transaction View
-- Joins Fact_Sales with all four dimensions to display human-readable facts.
-- ------------------------------------------------------------
SELECT 
    f.Sales_ID,
    f.InvoiceNo,
    d.FullDate,
    d.MonthName,
    d.YearNumber,
    p.StockCode,
    p.Description AS ProductDescription,
    c.CustomerCode,
    co.CountryName,
    f.Quantity,
    f.UnitPrice,
    f.TotalAmount
FROM Fact_Sales f
JOIN Dim_Date d ON f.Date_ID = d.Date_ID
JOIN Dim_Product p ON f.Product_ID = p.Product_ID
JOIN Dim_Customer c ON f.Customer_ID = c.Customer_ID
JOIN Dim_Country co ON f.Country_ID = co.Country_ID
ORDER BY f.Sales_ID DESC
LIMIT 10;

-- ------------------------------------------------------------
-- 3. OLAP Roll-up: Monthly & Yearly Sales Aggregation
-- Aggregates fine-grained sales into higher-level time summaries.
-- ------------------------------------------------------------
SELECT 
    d.YearNumber,
    d.MonthNumber,
    d.MonthName,
    COUNT(DISTINCT f.InvoiceNo) AS TotalInvoices,
    SUM(f.Quantity) AS TotalQuantity,
    ROUND(SUM(f.TotalAmount), 2) AS TotalRevenue,
    ROUND(AVG(f.TotalAmount), 2) AS AvgLineRevenue
FROM Fact_Sales f
JOIN Dim_Date d ON f.Date_ID = d.Date_ID
GROUP BY d.YearNumber, d.MonthNumber, d.MonthName
ORDER BY d.YearNumber, d.MonthNumber;

-- ------------------------------------------------------------
-- 4. OLAP Drill-down: Yearly -> Quarterly -> Monthly Breakdown
-- Navigates from summarized yearly data down to detailed quarters and months.
-- ------------------------------------------------------------
SELECT 
    d.YearNumber,
    d.QuarterNumber,
    d.MonthNumber,
    d.MonthName,
    SUM(f.TotalAmount) AS QuarterlyMonthlyRevenue
FROM Fact_Sales f
JOIN Dim_Date d ON f.Date_ID = d.Date_ID
GROUP BY d.YearNumber, d.QuarterNumber, d.MonthNumber, d.MonthName
ORDER BY d.YearNumber, d.QuarterNumber, d.MonthNumber;

-- ------------------------------------------------------------
-- 5. OLAP Slice: Single Dimension Filter (e.g., Country = 'United Kingdom')
-- Produces a 2D slice of the cube by fixing one dimension.
-- ------------------------------------------------------------
SELECT 
    co.CountryName,
    d.YearNumber,
    d.MonthName,
    COUNT(DISTINCT f.InvoiceNo) AS Invoices,
    ROUND(SUM(f.TotalAmount), 2) AS CountryRevenue
FROM Fact_Sales f
JOIN Dim_Country co ON f.Country_ID = co.Country_ID
JOIN Dim_Date d ON f.Date_ID = d.Date_ID
WHERE co.CountryName = 'United Kingdom'
GROUP BY co.CountryName, d.YearNumber, d.MonthName, d.MonthNumber
ORDER BY d.YearNumber, d.MonthNumber;

-- ------------------------------------------------------------
-- 6. OLAP Dice: Multi-Dimensional Sub-Cube Filtering
-- Filters on two or more dimensions simultaneously (Specific Countries + Specific Year).
-- ------------------------------------------------------------
SELECT 
    co.CountryName,
    d.YearNumber,
    p.StockCode,
    p.Description,
    SUM(f.Quantity) AS TotalQtySold,
    ROUND(SUM(f.TotalAmount), 2) AS TotalRevenue
FROM Fact_Sales f
JOIN Dim_Country co ON f.Country_ID = co.Country_ID
JOIN Dim_Date d ON f.Date_ID = d.Date_ID
JOIN Dim_Product p ON f.Product_ID = p.Product_ID
WHERE co.CountryName IN ('Germany', 'France', 'United Kingdom')
  AND d.YearNumber = 2011
GROUP BY co.CountryName, d.YearNumber, p.StockCode, p.Description
ORDER BY TotalRevenue DESC
LIMIT 20;

-- ------------------------------------------------------------
-- 7. Top 10 Best-Selling Products by Revenue
-- ------------------------------------------------------------
SELECT 
    p.Product_ID,
    p.StockCode,
    p.Description,
    SUM(f.Quantity) AS TotalUnitsSold,
    ROUND(SUM(f.TotalAmount), 2) AS TotalRevenue
FROM Fact_Sales f
JOIN Dim_Product p ON f.Product_ID = p.Product_ID
GROUP BY p.Product_ID, p.StockCode, p.Description
ORDER BY TotalRevenue DESC
LIMIT 10;

-- ------------------------------------------------------------
-- 8. Customer RFM Base Aggregates (For K-Means Clustering)
-- Extracts Recency (max date), Frequency (distinct invoices), and Monetary (total spend).
-- Excludes the UNKNOWN customer (Customer_ID = 1).
-- ------------------------------------------------------------
SELECT 
    c.Customer_ID,
    c.CustomerCode,
    MAX(d.FullDate) AS LastPurchaseDate,
    DATEDIFF((SELECT MAX(FullDate) FROM Dim_Date), MAX(d.FullDate)) AS RecencyDays,
    COUNT(DISTINCT f.InvoiceNo) AS Frequency,
    ROUND(SUM(f.TotalAmount), 2) AS Monetary
FROM Fact_Sales f
JOIN Dim_Customer c ON f.Customer_ID = c.Customer_ID
JOIN Dim_Date d ON f.Date_ID = d.Date_ID
WHERE c.Customer_ID <> 1
GROUP BY c.Customer_ID, c.CustomerCode;

-- ------------------------------------------------------------
-- 9. Market Basket Item Grouping (For Apriori Algorithm)
-- Groups distinct products purchased in the same invoice basket.
-- ------------------------------------------------------------
SELECT 
    f.InvoiceNo,
    GROUP_CONCAT(DISTINCT p.Description ORDER BY p.Description SEPARATOR ' | ') AS BasketItems,
    COUNT(DISTINCT p.Product_ID) AS BasketSize
FROM Fact_Sales f
JOIN Dim_Product p ON f.Product_ID = p.Product_ID
GROUP BY f.InvoiceNo
HAVING BasketSize > 1
LIMIT 20;
