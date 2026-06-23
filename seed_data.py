"""
运行方式: python seed_data.py
从 全局评价.csv 导入课程、老师和历史评价数据。
"""
import csv
import os
from app import create_app
from models import db, Course, Teacher, Evaluation

CSV_PATH = os.path.join(os.path.dirname(__file__), '全局评价.csv')
YEAR_COLS = [(2025, 5, 6), (2024, 7, 8), (2023, 9, 10)]  # (year, rating_col, comment_col)


def parse_rating(val):
    try:
        r = int(val.strip())
        return r if 1 <= r <= 5 else None
    except (ValueError, AttributeError):
        return None


def get_or_create(model, **kw):
    obj = model.query.filter_by(**kw).first()
    if not obj:
        obj = model(**kw)
        db.session.add(obj)
        db.session.flush()
    return obj


app = create_app()
with app.app_context():
    db.create_all()

    if Evaluation.query.filter(Evaluation.submitter_ip.like('seed_%')).count() > 0:
        print('已存在导入数据，跳过。如需重新导入请先清空 evaluation 表。')
        exit(0)

    cur_course = None
    cur_teacher = None
    eval_idx = 0
    eval_count = 0

    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader)  # 跳过表头

        for row in reader:
            # 补齐列数，防止短行报错
            while len(row) < 12:
                row.append('')

            code = row[0].strip()
            name = row[1].strip()
            teacher_name = row[2].strip()
            credits_str = row[4].strip()

            # 遇到无效课程代码，重置上下文
            if code in ('？', '公共选修'):
                cur_course = None
                cur_teacher = None
                continue

            # 新课程行
            if code:
                if not name:
                    cur_course = None
                    continue
                credits = float(credits_str) if credits_str else 0.0
                cur_course = Course.query.filter_by(code=code).first()
                if not cur_course:
                    cur_course = Course(code=code, name=name, credits=credits)
                    db.session.add(cur_course)
                    db.session.flush()
                else:
                    cur_course.name = name
                    cur_course.credits = credits
                cur_teacher = None

            if not cur_course:
                continue

            # 新老师行
            if teacher_name and teacher_name != '？':
                cur_teacher = get_or_create(Teacher, name=teacher_name)
                if cur_teacher not in cur_course.teachers:
                    cur_course.teachers.append(cur_teacher)

            if not cur_teacher:
                continue

            # 导入评价
            for year, r_col, c_col in YEAR_COLS:
                rating = parse_rating(row[r_col])
                if rating is None:
                    continue
                comment = row[c_col].strip() or None
                eval_idx += 1
                db.session.add(Evaluation(
                    course_id=cur_course.id,
                    teacher_id=cur_teacher.id,
                    year=year,
                    rating=rating,
                    comment=comment,
                    submitter_ip=f'seed_{eval_idx}',
                ))
                eval_count += 1

    db.session.commit()
    print(f'导入完成：{eval_count} 条评价记录。')
