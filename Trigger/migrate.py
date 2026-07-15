import sqlite3
from db import get_db_connection

def run_migration():
    """
    Migration script to upgrade the MVP 'appointments' schema.
    Safely drops the legacy table and establishes explicit 'date' and 'time' constraints
    aligning with Phase 4 production-orientated modular structures.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("Beginning migration -> Phase 4 Appointments Schema Drop/Rebuild...")
    
    try:
        # Explicit Drop
        cursor.execute("DROP TABLE IF EXISTS appointments")
        
        # Explicit Recreate with isolated date and time natively
        cursor.execute('''
            CREATE TABLE appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        print("Schema successfully migrated to isolated Date/Time columns.")
    except Exception as e:
        conn.rollback()
        print(f"Migration Failed: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()
