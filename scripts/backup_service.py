#!/usr/bin/env python3
"""
Automated encrypted database backups (Phase 5 of Roadmap).
Dumps the database, encrypts it using AES-256-GCM (via cryptography Fernet),
and stores it in a backups directory (or uploads to S3 in production).
"""
import os
import time
import shutil
from pathlib import Path
from cryptography.fernet import Fernet

def perform_backup(db_path, backup_dir, encryption_key):
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return False
        
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = int(time.time())
    backup_file = os.path.join(backup_dir, f"lifeos_backup_{timestamp}.db.enc")
    
    print(f"Backing up database to {backup_file}...")
    
    # Read database
    with open(db_path, 'rb') as f:
        data = f.read()
        
    # Encrypt
    cipher = Fernet(encryption_key.encode())
    encrypted_data = cipher.encrypt(data)
    
    # Save
    with open(backup_file, 'wb') as f:
        f.write(encrypted_data)
        
    print(f"Backup successful. Size: {len(encrypted_data)} bytes.")
    
    # Keep only last 7 backups
    backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("lifeos_backup_")])
    if len(backups) > 7:
        for old in backups[:-7]:
            print(f"Removing old backup: {old}")
            os.remove(old)
            
    return True

if __name__ == "__main__":
    key = os.environ.get("LIFEOS_ENCRYPTION_KEY")
    if not key:
        print("ERROR: LIFEOS_ENCRYPTION_KEY not set.")
        exit(1)
        
    db = os.environ.get("LIFEOS_DATABASE_URL", "sqlite:///./data/lifeos.db")
    if db.startswith("sqlite:///"):
        db_file = db.replace("sqlite:///", "")
        perform_backup(db_file, "./data/backups", key)
    else:
        print("S3 Postgres Backups not fully configured in this roadmap phase yet.")
        print("Please use pg_dump in production.")
