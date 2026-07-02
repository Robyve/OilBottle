from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# 课程-老师 多对多关联表
course_teacher = db.Table(
    'course_teacher',
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True),
    db.Column('teacher_id', db.Integer, db.ForeignKey('teacher.id'), primary_key=True),
)

# 评价-标签 多对多关联表
evaluation_tag = db.Table(
    'evaluation_tag',
    db.Column('evaluation_id', db.Integer, db.ForeignKey('evaluation.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    credits = db.Column(db.Float, nullable=False)
    exclude_from_public = db.Column(db.Boolean, default=False, nullable=False)
    teachers = db.relationship('Teacher', secondary=course_teacher, back_populates='courses')
    evaluations = db.relationship('Evaluation', back_populates='course', lazy='dynamic')
    curriculum = db.relationship('CurriculumEntry', back_populates='course', lazy='dynamic')


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    courses = db.relationship('Course', secondary=course_teacher, back_populates='teachers')
    evaluations = db.relationship('Evaluation', back_populates='teacher', lazy='dynamic')


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(30), nullable=False)
    __table_args__ = (db.UniqueConstraint('category', 'label'),)


class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Integer, nullable=True)  # 1-5, optional
    comment = db.Column(db.Text)
    submitter_ip = db.Column(db.String(45), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course', back_populates='evaluations')
    teacher = db.relationship('Teacher', back_populates='evaluations')
    tags = db.relationship('Tag', secondary=evaluation_tag)
    __table_args__ = (
        db.UniqueConstraint('course_id', 'teacher_id', 'year', 'submitter_ip',
                            name='uq_one_eval_per_ip'),
    )


class CurriculumEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    student_type = db.Column(db.String(10), nullable=False)
    major_category = db.Column(db.String(20), nullable=False)   # 课程大类
    sub_category = db.Column(db.String(30), nullable=False)     # 课程类别
    sort_order = db.Column(db.Integer, default=0)
    course = db.relationship('Course', back_populates='curriculum')
    __table_args__ = (db.UniqueConstraint('course_id', 'year', 'student_type'),)


class SiteConfig(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, default='')


class PageView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), nullable=False)
    ts = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
