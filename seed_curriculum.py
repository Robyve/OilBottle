"""
运行方式: python seed_curriculum.py
从 csv/培养方案/ 目录下的 CSV 文件导入培养方案数据。
文件命名规则: {两位年份}{类型}.csv，例如 25专硕.csv → year=2025, student_type=专硕
"""
import csv
import os
import re
from app import create_app
from models import db, Course, CurriculumEntry

CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv', '培养方案')


def parse_filename(filename):
    m = re.match(r'^(\d{2})(.+)\.csv$', filename)
    if not m:
        return None, None
    year = 2000 + int(m.group(1))
    student_type = m.group(2)
    return year, student_type


def get_or_create_course(code, name, credits_str):
    course = Course.query.filter_by(code=code).first()
    if not course:
        try:
            credits = float(credits_str) if credits_str else 0.0
        except ValueError:
            credits = 0.0
        course = Course(code=code, name=name, credits=credits)
        db.session.add(course)
        db.session.flush()
    return course


app = create_app()
with app.app_context():
    db.create_all()

    total = 0
    for filename in sorted(os.listdir(CSV_DIR)):
        if not filename.endswith('.csv'):
            continue
        year, student_type = parse_filename(filename)
        if not year:
            print(f'跳过无法解析的文件名: {filename}')
            continue

        # 删除该年份+类型的旧数据，重新导入
        CurriculumEntry.query.filter_by(year=year, student_type=student_type).delete()

        path = os.path.join(CSV_DIR, filename)
        with open(path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            sort_order = 0
            for row in reader:
                code = row.get('课程编号', '').strip()
                if not code:
                    continue
                name = row.get('课程中文名称', '').strip()
                credits_str = row.get('学分', '').strip()
                major_cat = row.get('课程大类', '').strip()
                sub_cat = row.get('课程类别', '').strip()

                course = get_or_create_course(code, name, credits_str)
                db.session.add(CurriculumEntry(
                    course_id=course.id,
                    year=year,
                    student_type=student_type,
                    major_category=major_cat,
                    sub_category=sub_cat,
                    sort_order=sort_order,
                ))
                sort_order += 1
                total += 1

        db.session.commit()
        print(f'[{filename}] → {year} {student_type}，{sort_order} 条')

    print(f'\n培养方案导入完成：共 {total} 条。')
