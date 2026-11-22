"""SQLAlchemy ORM Models for SmartMart Analytics Dimensional Data Warehouse.

Implements the Star Schema:
- DimProduct
- DimCustomer
- DimDate
- DimCountry
- FactSales
"""

from database import db


class DimProduct(db.Model):
    """Product Dimension table."""
    __tablename__ = 'Dim_Product'

    Product_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    StockCode = db.Column(db.String(50), nullable=False, unique=True, index=True)
    Description = db.Column(db.String(255), nullable=True)

    sales = db.relationship('FactSales', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'Product_ID': self.Product_ID,
            'StockCode': self.StockCode,
            'Description': self.Description
        }


class DimCustomer(db.Model):
    """Customer Dimension table."""
    __tablename__ = 'Dim_Customer'

    Customer_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CustomerCode = db.Column(db.String(50), nullable=False, unique=True, index=True)

    sales = db.relationship('FactSales', backref='customer', lazy='dynamic')

    def to_dict(self):
        return {
            'Customer_ID': self.Customer_ID,
            'CustomerCode': self.CustomerCode
        }


class DimDate(db.Model):
    """Calendar Date Dimension table.

    Date_ID format: YYYYMMDD as an integer.
    """
    __tablename__ = 'Dim_Date'

    Date_ID = db.Column(db.Integer, primary_key=True)
    FullDate = db.Column(db.Date, nullable=False, index=True)
    DayNumber = db.Column(db.SmallInteger, nullable=False)
    MonthNumber = db.Column(db.SmallInteger, nullable=False)
    MonthName = db.Column(db.String(20), nullable=False)
    QuarterNumber = db.Column(db.SmallInteger, nullable=False)
    YearNumber = db.Column(db.SmallInteger, nullable=False)

    sales = db.relationship('FactSales', backref='date', lazy='dynamic')

    def to_dict(self):
        return {
            'Date_ID': self.Date_ID,
            'FullDate': str(self.FullDate),
            'DayNumber': self.DayNumber,
            'MonthNumber': self.MonthNumber,
            'MonthName': self.MonthName,
            'QuarterNumber': self.QuarterNumber,
            'YearNumber': self.YearNumber
        }


class DimCountry(db.Model):
    """Country Dimension table."""
    __tablename__ = 'Dim_Country'

    Country_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CountryName = db.Column(db.String(100), nullable=False, unique=True, index=True)

    sales = db.relationship('FactSales', backref='country', lazy='dynamic')

    def to_dict(self):
        return {
            'Country_ID': self.Country_ID,
            'CountryName': self.CountryName
        }


class FactSales(db.Model):
    """Central Fact Table for Sales.

    Grain: One product line item within one invoice.
    """
    __tablename__ = 'Fact_Sales'

    Sales_ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    InvoiceNo = db.Column(db.String(50), nullable=False, index=True)
    Product_ID = db.Column(
        db.Integer,
        db.ForeignKey('Dim_Product.Product_ID', ondelete='RESTRICT', onupdate='CASCADE'),
        nullable=False,
        index=True
    )
    Customer_ID = db.Column(
        db.Integer,
        db.ForeignKey('Dim_Customer.Customer_ID', ondelete='RESTRICT', onupdate='CASCADE'),
        nullable=False,
        index=True
    )
    Date_ID = db.Column(
        db.Integer,
        db.ForeignKey('Dim_Date.Date_ID', ondelete='RESTRICT', onupdate='CASCADE'),
        nullable=False,
        index=True
    )
    Country_ID = db.Column(
        db.Integer,
        db.ForeignKey('Dim_Country.Country_ID', ondelete='RESTRICT', onupdate='CASCADE'),
        nullable=False,
        index=True
    )
    Quantity = db.Column(db.Integer, nullable=False)
    UnitPrice = db.Column(db.Numeric(10, 2), nullable=False)
    TotalAmount = db.Column(db.Numeric(12, 2), nullable=False)

    def to_dict(self):
        return {
            'Sales_ID': self.Sales_ID,
            'InvoiceNo': self.InvoiceNo,
            'Product_ID': self.Product_ID,
            'Customer_ID': self.Customer_ID,
            'Date_ID': self.Date_ID,
            'Country_ID': self.Country_ID,
            'Quantity': self.Quantity,
            'UnitPrice': float(self.UnitPrice),
            'TotalAmount': float(self.TotalAmount)
        }
