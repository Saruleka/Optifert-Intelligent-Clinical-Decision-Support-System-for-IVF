import sqlite3
import os

DB_PATH = 'ivf_clinic.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Turn on foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'patient',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Doctor Profiles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            specialty TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create Patient Profiles
    # Note: doctor_id is nullable (patients might register before linking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            doctor_id INTEGER,
            age INTEGER,
            last_visit TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')

    # Create Appointments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
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

    # Create Alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'low',
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Create Cycles (Prediction History)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            
            -- Inputs
            age REAL, bmi REAL, amh REAL, afc REAL,
            protocol TEXT, gon REAL, stim_days REAL,
            f12 REAL, f18 REAL, f22 REAL, lead_follicle REAL,
            e2 REAL, e2_prev REAL, lh REAL, growth REAL,
            
            -- ML Outputs
            predicted_trigger TEXT,
            confidence REAL,
            ohss_risk TEXT,
            estimated_mii INTEGER,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully with Phase 2 schemas.")
