import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from db import get_db_connection, init_db

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create dummy users
    doctor_pass = generate_password_hash("doctor123")
    patient_pass = generate_password_hash("patient123")
    
    # Check if they exist first to avoid integrity errors on re-runs
    check_doc = cursor.execute("SELECT id FROM users WHERE email='dr.smith@optifert.com'").fetchone()
    if not check_doc:
        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("Dr. John Smith", "dr.smith@optifert.com", doctor_pass, "doctor"))
        doc_id = cursor.lastrowid
        cursor.execute("INSERT INTO doctor_profiles (user_id, specialty) VALUES (?, ?)", (doc_id, "Reproductive Endocrinology"))
        
        # Add a couple of dummy patients
        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("Alice Hart", "alice@test.com", patient_pass, "patient"))
        alice_id = cursor.lastrowid
        cursor.execute("INSERT INTO patient_profiles (user_id, doctor_id, age) VALUES (?, ?, ?)", (alice_id, doc_id, 32))

        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("Sarah Jenkins", "sarah@test.com", patient_pass, "patient"))
        sarah_id = cursor.lastrowid
        cursor.execute("INSERT INTO patient_profiles (user_id, doctor_id, age) VALUES (?, ?, ?)", (sarah_id, doc_id, 29))
        
        # Add appointments for today natively splitting Date and Time elements
        today = datetime.now()
        today_date = today.strftime("%Y-%m-%d")
        
        cursor.execute("INSERT INTO appointments (doctor_id, patient_id, date, time, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                       (doc_id, alice_id, today_date, "10:00", "scheduled", "Baseline follicle check."))
        cursor.execute("INSERT INTO appointments (doctor_id, patient_id, date, time, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                       (doc_id, sarah_id, today_date, "14:30", "scheduled", "First trigger sizing check."))

        # Add some alerts
        cursor.execute("INSERT INTO alerts (doctor_id, patient_id, message, severity) VALUES (?, ?, ?, ?)",
                       (doc_id, alice_id, "E2 levels rising faster than expected.", "high"))
        cursor.execute("INSERT INTO alerts (doctor_id, patient_id, message, severity) VALUES (?, ?, ?, ?)",
                       (doc_id, sarah_id, "Follicle scan required for mapping.", "medium"))

        print("Seed data inserted successfully.")
    else:
        print("Doctor already exists. DB not seeded again.")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Initialize schema first
    init_db()
    seed_data()
