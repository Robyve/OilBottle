"""
运行方式: python init_db.py
创建数据库表、预置标签、创建管理员账号。
"""
from app import create_app
from models import db, Admin, Tag

TAGS = [
    ('考核', 'MOOC/不用到场'), ('考勤', '不点名'), ('考勤', '偶尔点名'), ('考勤', '严格点名'),
    ('作业', '无作业'), ('作业', '作业少'), ('作业', '作业多'),
    ('给分', '捞不及格'), 
    ('上课', '互动多'), ('上课', '讲得清楚'),
    ('考核', '有期末考试'), ('考核', '考核方式灵活'),
]

app = create_app()
with app.app_context():
    db.create_all()

    for category, label in TAGS:
        if not Tag.query.filter_by(category=category, label=label).first():
            db.session.add(Tag(category=category, label=label))

    username = input('管理员用户名 [admin]: ').strip() or 'admin'
    password = input('管理员密码: ').strip()
    if not password:
        print('密码不能为空，已中止。')
        exit(1)

    existing = Admin.query.filter_by(username=username).first()
    if existing:
        existing.set_password(password)
        print(f'已更新管理员「{username}」的密码。')
    else:
        admin = Admin(username=username)
        admin.set_password(password)
        db.session.add(admin)
        print(f'管理员「{username}」创建成功。')

    db.session.commit()
    print('数据库初始化完成。')
