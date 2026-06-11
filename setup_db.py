"""デモ用SQLiteデータベース作成（製造業：商品・在庫・取引先）"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")


def setup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # --- 取引先 ---
    c.execute("""
        CREATE TABLE suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT,
            region TEXT,
            lead_days INTEGER
        )
    """)
    suppliers = [
        ("S001", "東海部品工業", "愛知", 3),
        ("S002", "関東精密", "埼玉", 5),
        ("S003", "九州金属", "福岡", 7),
        ("S004", "大阪機工", "大阪", 4),
    ]
    c.executemany("INSERT INTO suppliers VALUES (?,?,?,?)", suppliers)

    # --- 商品 ---
    c.execute("""
        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            unit_price INTEGER,
            supplier_id TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        )
    """)
    products = [
        ("P001", "ベアリング A-100", "軸受", 1200, "S001"),
        ("P002", "ベアリング A-200", "軸受", 1800, "S001"),
        ("P003", "シャフト B-50", "軸部品", 3500, "S002"),
        ("P004", "ギア C-30", "歯車", 2200, "S003"),
        ("P005", "ギア C-60", "歯車", 4100, "S003"),
        ("P006", "Oリング D-10", "シール", 150, "S004"),
        ("P007", "Oリング D-20", "シール", 280, "S004"),
        ("P008", "カップリング E-5", "継手", 5600, "S002"),
        ("P009", "フランジ F-12", "継手", 3200, "S001"),
        ("P010", "ボルトセット G-8", "締結", 450, "S004"),
    ]
    c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

    # --- 在庫 ---
    c.execute("""
        CREATE TABLE inventory (
            product_id TEXT PRIMARY KEY,
            stock_qty INTEGER,
            safety_stock INTEGER,
            warehouse TEXT,
            last_updated TEXT,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)
    inventory = [
        ("P001", 250, 100, "本社倉庫", "2026-05-31"),
        ("P002", 30, 50, "本社倉庫", "2026-05-31"),   # ★欠品リスク
        ("P003", 80, 30, "第2倉庫", "2026-05-31"),
        ("P004", 15, 40, "本社倉庫", "2026-05-31"),   # ★欠品リスク
        ("P005", 60, 20, "本社倉庫", "2026-05-31"),
        ("P006", 500, 200, "第2倉庫", "2026-05-31"),
        ("P007", 180, 150, "第2倉庫", "2026-05-31"),
        ("P008", 5, 10, "本社倉庫", "2026-05-31"),    # ★欠品リスク
        ("P009", 90, 40, "本社倉庫", "2026-05-31"),
        ("P010", 1200, 500, "第2倉庫", "2026-05-31"),
    ]
    c.executemany("INSERT INTO inventory VALUES (?,?,?,?,?)", inventory)

    # --- 発注 ---
    c.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            product_id TEXT,
            quantity INTEGER,
            order_date TEXT,
            due_date TEXT,
            status TEXT,
            supplier_id TEXT,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        )
    """)
    orders = [
        ("ORD-2026-041", "P001", 100, "2026-04-10", "2026-04-13", "納品済", "S001"),
        ("ORD-2026-042", "P003", 30,  "2026-04-12", "2026-04-17", "納品済", "S002"),
        ("ORD-2026-043", "P006", 200, "2026-04-15", "2026-04-19", "納品済", "S004"),
        ("ORD-2026-044", "P004", 40,  "2026-04-18", "2026-04-25", "納品済", "S003"),
        ("ORD-2026-045", "P009", 50,  "2026-04-22", "2026-04-25", "納品済", "S001"),
        ("ORD-2026-051", "P001", 100, "2026-05-02", "2026-05-05", "納品済", "S001"),
        ("ORD-2026-052", "P002", 80,  "2026-05-02", "2026-05-05", "納品済", "S001"),
        ("ORD-2026-053", "P004", 50,  "2026-05-08", "2026-05-15", "納品済", "S003"),
        ("ORD-2026-054", "P006", 300, "2026-05-10", "2026-05-14", "納品済", "S004"),
        ("ORD-2026-055", "P003", 20,  "2026-05-15", "2026-05-20", "納品済", "S002"),
        ("ORD-2026-056", "P008", 10,  "2026-05-18", "2026-05-23", "納品済", "S002"),
        ("ORD-2026-057", "P002", 30,  "2026-05-20", "2026-05-23", "遅延",   "S001"),
        ("ORD-2026-058", "P005", 40,  "2026-05-22", "2026-05-29", "納品済", "S003"),
        ("ORD-2026-059", "P004", 30,  "2026-05-25", "2026-06-01", "未納品", "S003"),
        ("ORD-2026-060", "P009", 25,  "2026-05-28", "2026-05-31", "納品済", "S001"),
        ("ORD-2026-061", "P007", 100, "2026-05-30", "2026-06-03", "未納品", "S004"),
    ]
    c.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", orders)

    conn.commit()
    conn.close()
    print(f"DB作成完了: {DB_PATH}")
    print(f"  - suppliers: {len(suppliers)}件")
    print(f"  - products: {len(products)}件")
    print(f"  - inventory: {len(inventory)}件")
    print(f"  - orders: {len(orders)}件")


if __name__ == "__main__":
    setup()
