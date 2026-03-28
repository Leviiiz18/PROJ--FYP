import sqlite3
import os
from pathlib import Path

# DB Path to export
DB_PATH = Path("d:/code/kt/mock_test/exam_data.db").resolve()
OUTPUT_FILE = Path("d:/code/kt/database_dump.txt").resolve()

def dump_database():
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        return

    print(f"📄 Dumping Database: {DB_PATH}")
    print(f"💾 Saving to: {OUTPUT_FILE}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # 1. Attempts Table
            f.write("="*80 + "\n")
            f.write(" TABLE: attempts (Historical Scores)\n")
            f.write("="*80 + "\n")
            
            cursor.execute("SELECT * FROM attempts")
            columns = [c[0] for c in cursor.description]
            f.write(f"{' | '.join(columns)}\n")
            f.write("-" * 80 + "\n")
            
            for row in cursor.fetchall():
                f.write(f"{' | '.join(map(str, row))}\n")
            
            f.write("\n\n" + "="*80 + "\n")
            f.write(" TABLE: textbook_cache (Pre-parsed context)\n")
            f.write("="*80 + "\n")
            
            cursor.execute("SELECT subject, chapter, grade, length(content) FROM textbook_cache")
            f.write("Subject | Chapter | Grade | Content Size (Chars)\n")
            f.write("-" * 80 + "\n")
            for row in cursor.fetchall():
                f.write(f"{' | '.join(map(str, row))}\n")
        
        conn.close()
        print("✅ Export complete!")
    except Exception as e:
        print(f"❌ Error during dump: {e}")

if __name__ == "__main__":
    dump_database()
