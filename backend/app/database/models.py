import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.connection import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), default="Packaged Food")
    brand = Column(String(100), nullable=True)
    barcode = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scans = relationship("ScanResult", back_populates="product", cascade="all, delete-orphan")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    image_url = Column(String(500), nullable=False)
    image_filename = Column(String(255), nullable=False)
    extracted_data = Column(JSON, nullable=False)  # Raw and structured OCR extractions
    compliance_score = Column(Float, nullable=False)
    compliance_status = Column(String(50), nullable=False)  # PASS, FAIL, WARNING
    risk_level = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    product = relationship("Product", back_populates="scans")
    reports = relationship("Report", back_populates="scan", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scan_results.id"), nullable=False)
    report_code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    violations_count = Column(Integer, default=0)
    warnings_count = Column(Integer, default=0)
    passed_count = Column(Integer, default=0)
    details = Column(JSON, nullable=False)  # Breakdown of all 7 mandatory rules
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("ScanResult", back_populates="reports")
