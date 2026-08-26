# -*- coding: utf-8 -*-
"""بيانات تجريبية للنظام - تشغيل: python seed.py"""
from datetime import date, timedelta
from database import db
from app import create_app
from models import (
    Employee, Project, RealEstateUnit, Customer, Supplier,
    Invoice, PurchaseOrder, RentalContract,
)

app = create_app()


def seed():
    with app.app_context():
        # تنظيف الجداول
        for model in [RentalContract, PurchaseOrder, Invoice, RealEstateUnit,
                      Customer, Supplier, Project, Employee]:
            model.query.delete()
        db.session.commit()

        # الموظفين
        employees = [
            Employee(full_name="أحمد محمد", department="الهندسة", position="مهندس مدني",
                     phone="0551111111", email="ahmed@mokawlat.com", salary=18000),
            Employee(full_name="سارة علي", department="المالية", position="محاسبة",
                     phone="0552222222", email="sara@mokawlat.com", salary=15000),
            Employee(full_name="خالد حسن", department="المبيعات", position="مدير مبيعات",
                     phone="0553333333", email="khaled@mokawlat.com", salary=20000),
            Employee(full_name="نورا سعيد", department="الموارد البشرية", position="أخصائية موارد بشرية",
                     phone="0554444444", email="noura@mokawlat.com", salary=14000),
            Employee(full_name="عمر خالد", department="المخازن", position="أمين مخزن",
                     phone="0555555555", email="omar@mokawlat.com", salary=9000),
            Employee(full_name="فاطمة أحمد", department="المالية", position="محاسبة",
                     phone="0556666666", email="fatma@mokawlat.com", salary=15000),
            Employee(full_name="محمد علي", department="الهندسة", position="مهندس موقع",
                     phone="0557777777", email="mohamed@mokawlat.com", salary=16000),
        ]
        db.session.add_all(employees)
        db.session.commit()

        # المشاريع
        emp1, emp7 = employees[0], employees[6]
        projects = [
            Project(name="برج النيل", location="الرياض - حي النرجس", status="active",
                    priority="high", budget=8700000, spent=3900000, completion=45,
                    deadline=date(2027, 6, 30), manager=emp1,
                    description="برج سكني تجاري من 12 طابق"),
            Project(name="مشروع الواحة", location="جدة - أبحر", status="active",
                    priority="medium", budget=5200000, spent=3100000, completion=60,
                    deadline=date(2026, 12, 15), manager=emp7,
                    description="مجمع فلل سكنية فاخرة"),
            Project(name="مجمع الزهراء", location="الدمام - الشاطئ", status="finishing",
                    priority="high", budget=3100000, spent=2800000, completion=90,
                    deadline=date(2026, 8, 20), manager=emp1,
                    description="مجمع تجاري سكني"),
            Project(name="مدينة الرياض", location="الرياض - حي الملقا", status="active",
                    priority="low", budget=12500000, spent=3700000, completion=25,
                    deadline=date(2028, 1, 1), manager=emp7,
                    description="مشروع متعدد الاستخدامات"),
        ]
        db.session.add_all(projects)
        db.session.commit()

        # الوحدات العقارية
        proj_by_name = {p.name: p for p in projects}
        units = [
            RealEstateUnit(unit_code="A-101", project=proj_by_name["برج النيل"], unit_type="شقة", area=150, floor="1", price=2500000, status="available"),
            RealEstateUnit(unit_code="A-102", project=proj_by_name["برج النيل"], unit_type="شقة", area=150, floor="1", price=2500000, status="reserved"),
            RealEstateUnit(unit_code="B-201", project=proj_by_name["برج النيل"], unit_type="بنتهاوس", area=250, floor="3", price=5500000, status="sold"),
            RealEstateUnit(unit_code="C-101", project=proj_by_name["مشروع الواحة"], unit_type="فيلا", area=350, floor="1", price=8000000, status="available"),
            RealEstateUnit(unit_code="C-102", project=proj_by_name["مشروع الواحة"], unit_type="فيلا", area=400, floor="1", price=10000000, status="sold"),
            RealEstateUnit(unit_code="D-101", project=proj_by_name["مجمع الزهراء"], unit_type="شقة", area=120, floor="2", price=1500000, status="rented"),
            RealEstateUnit(unit_code="D-102", project=proj_by_name["مجمع الزهراء"], unit_type="محل", area=80, floor="0", price=1200000, status="available"),
            RealEstateUnit(unit_code="E-101", project=proj_by_name["مدينة الرياض"], unit_type="شقة", area=180, floor="5", price=3200000, status="reserved"),
        ]
        db.session.add_all(units)
        db.session.commit()

        # العملاء
        customers = [
            Customer(full_name="شركة البنيان", type="company", phone="0111111111", email="info@elbonyan.com", address="الرياض"),
            Customer(full_name="مؤسسة الأفق", type="company", phone="0122222222", email="info@alofoq.com", address="جدة"),
            Customer(full_name="عبدالله العتيبي", type="individual", phone="0533333333", email="abdullah@example.com", address="الدمام"),
            Customer(full_name="سعد القحطاني", type="individual", phone="0544444444", email="saad@example.com", address="الرياض"),
        ]
        db.session.add_all(customers)
        db.session.commit()

        # الموردين
        suppliers = [
            Supplier(company_name="شركة الأهرام للمواد", contact_name="محمد إبراهيم", phone="0133333333", category="مواد بناء"),
            Supplier(company_name="مصنع النور للسبك", contact_name="حسن النور", phone="0144444444", category="معدات"),
            Supplier(company_name="مؤسسة البنيان", contact_name="خالد البنيان", phone="0155555555", category="مقاول"),
            Supplier(company_name="شركة الكهرباء العربية", contact_name="فهد العيسى", phone="0166666666", category="خدمات"),
        ]
        db.session.add_all(suppliers)
        db.session.commit()

        # الفواتير
        today = date.today()
        customer1, customer2, customer4 = customers[0], customers[1], customers[3]
        supplier1, supplier3 = suppliers[0], suppliers[2]
        proj1, proj2, proj4 = proj_by_name["برج النيل"], proj_by_name["مشروع الواحة"], proj_by_name["مدينة الرياض"]
        invoices = [
            Invoice(invoice_number="INV-1001", invoice_type="sales", customer=customer1, project=proj1,
                    amount=5500000, paid_amount=5500000, status="paid",
                    issue_date=today - timedelta(days=30), description="بيع وحدة B-201 - برج النيل"),
            Invoice(invoice_number="INV-1002", invoice_type="sales", customer=customer2, project=proj2,
                    amount=10000000, paid_amount=4000000, status="partial",
                    issue_date=today - timedelta(days=15), description="بيع فيلا C-102 - مشروع الواحة"),
            Invoice(invoice_number="INV-1003", invoice_type="purchase", supplier=supplier1, project=proj1,
                    amount=450000, paid_amount=200000, status="partial",
                    issue_date=today - timedelta(days=10), description="أسمنت وحديد تسليح"),
            Invoice(invoice_number="INV-1004", invoice_type="purchase", supplier=supplier3, project=proj2,
                    amount=750000, paid_amount=750000, status="paid",
                    issue_date=today - timedelta(days=20), description="أعمال مقاولات - مرحلة 2"),
            Invoice(invoice_number="INV-1005", invoice_type="sales", customer=customer4, project=proj4,
                    amount=3200000, paid_amount=0, status="pending",
                    issue_date=today - timedelta(days=5), description="حجز وحدة E-101 - مدينة الرياض"),
        ]
        db.session.add_all(invoices)
        db.session.commit()

        # أوامر الشراء
        s1, s2, s3, s4 = suppliers
        purchase_orders = [
            PurchaseOrder(po_number="PO-1001", supplier=s1, project=proj1,
                          items_description="أسمنت - حديد تسليح", total=450000, status="pending",
                          order_date=today - timedelta(days=2)),
            PurchaseOrder(po_number="PO-1002", supplier=s2, project=proj2,
                          items_description="سبائك حديد", total=1200000, status="approved",
                          order_date=today - timedelta(days=5)),
            PurchaseOrder(po_number="PO-1003", supplier=s3, project=proj_by_name["مجمع الزهراء"],
                          items_description="طوب أحمر", total=320000, status="delivered",
                          order_date=today - timedelta(days=7)),
            PurchaseOrder(po_number="PO-1004", supplier=s4, project=proj4,
                          items_description="أسلاك كهربائية", total=95000, status="pending",
                          order_date=today - timedelta(days=1)),
        ]
        db.session.add_all(purchase_orders)
        db.session.commit()

        # عقود الإيجار
        unit6 = units[5]  # D-101
        rentals = [
            RentalContract(contract_number="RC-1001", unit=unit6, customer=customers[2],
                           monthly_rent=12000, status="active",
                           start_date=today - timedelta(days=60), end_date=today + timedelta(days=305)),
        ]
        db.session.add_all(rentals)
        db.session.commit()

        print("تمت إضافة البيانات التجريبية بنجاح!")


if __name__ == "__main__":
    seed()
