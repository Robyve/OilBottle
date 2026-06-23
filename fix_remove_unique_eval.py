import sqlite3, os
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'course_eval.db')
con = sqlite3.connect(db_path)
con.executescript("""
PRAGMA foreign_keys=OFF;
BEGIN;
CREATE TABLE evaluation_new (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES course(id),
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    year INTEGER NOT NULL,
    rating INTEGER,
    comment TEXT,
    submitter_ip VARCHAR(45) NOT NULL,
    created_at DATETIME
);
INSERT INTO evaluation_new SELECT * FROM evaluation;
DROP TABLE evaluation;
ALTER TABLE evaluation_new RENAME TO evaluation;
COMMIT;
PRAGMA foreign_keys=ON;
""")
con.close()
print("Done.")
