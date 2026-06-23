import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///course_eval.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    YEARS = [2025, 2024, 2023, 2022, 2021]
    STUDENT_TYPES = ['专硕', '学硕', '专博', '学博']
    STUDENT_TYPE_ABBR = {'专硕': '专', '学硕': '学', '专博': '专博', '学博': '博'}
    ALLOW_MULTI_EVAL = True
