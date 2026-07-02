from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required
from sqlalchemy import func
from datetime import datetime, timedelta
from models import db, Admin, Course, Teacher, Tag, Evaluation, CurriculumEntry, SiteConfig, PageView
from config import Config


def _public_ids():
    has = {r[0] for r in db.session.query(CurriculumEntry.course_id).distinct().all()}
    return {c.id for c in Course.query.filter_by(exclude_from_public=False).all()
            if c.id not in has}

bp = Blueprint('admin', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        admin = Admin.query.filter_by(username=request.form['username']).first()
        if admin and admin.check_password(request.form['password']):
            login_user(admin)
            return redirect(url_for('admin.dashboard'))
        flash('用户名或密码错误', 'danger')
    return render_template('admin/login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


@bp.route('/')
@login_required
def dashboard():
    courses = Course.query.order_by(Course.code).all()
    teachers = Teacher.query.order_by(Teacher.name).all()
    tags = Tag.query.order_by(Tag.category, Tag.label).all()
    recent_evals = Evaluation.query.order_by(Evaluation.created_at.desc()).limit(20).all()
    curriculum = CurriculumEntry.query.order_by(
        CurriculumEntry.year.desc(), CurriculumEntry.student_type).all()
    ann = SiteConfig.query.get('announcement')
    return render_template('admin/dashboard.html',
                           courses=courses, teachers=teachers, tags=tags,
                           recent_evals=recent_evals, curriculum=curriculum,
                           years=Config.YEARS, student_types=Config.STUDENT_TYPES,
                           public_ids=_public_ids(),
                           announcement_html=ann.value if ann else '')


@bp.route('/announcement', methods=['POST'])
@login_required
def save_announcement():
    content = request.form.get('content', '')
    cfg = SiteConfig.query.get('announcement')
    if cfg:
        cfg.value = content
    else:
        db.session.add(SiteConfig(key='announcement', value=content))
    db.session.commit()
    flash('公告已保存', 'success')
    return redirect(url_for('admin.dashboard') + '#tab-announcement')


# --- Course CRUD ---

@bp.route('/course/<int:cid>/edit', methods=['POST'])
@login_required
def edit_course(cid):
    course = Course.query.get_or_404(cid)
    credits = request.form.get('credits', type=float)
    if credits is None or credits <= 0:
        flash('学分无效', 'danger')
    else:
        course.credits = credits
        db.session.commit()
    return redirect(url_for('admin.dashboard'))


@bp.route('/course/<int:cid>/toggle_public', methods=['POST'])
@login_required
def toggle_public(cid):
    course = Course.query.get_or_404(cid)
    course.exclude_from_public = not course.exclude_from_public
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@bp.route('/course/add', methods=['POST'])
@login_required
def add_course():
    code = request.form['code'].strip()
    name = request.form['name'].strip()
    credits = request.form.get('credits', type=float)
    teacher_ids = request.form.getlist('teacher_ids', type=int)
    if not code or not name or credits is None:
        flash('请填写完整课程信息', 'danger')
        return redirect(url_for('admin.dashboard'))
    if Course.query.filter_by(code=code).first():
        flash('课程编号已存在', 'danger')
        return redirect(url_for('admin.dashboard'))
    course = Course(code=code, name=name, credits=credits)
    if teacher_ids:
        course.teachers = Teacher.query.filter(Teacher.id.in_(teacher_ids)).all()
    db.session.add(course)
    db.session.commit()
    flash('课程添加成功', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/course/<int:cid>/delete', methods=['POST'])
@login_required
def delete_course(cid):
    course = Course.query.get_or_404(cid)
    db.session.delete(course)
    db.session.commit()
    flash('课程已删除', 'success')
    return redirect(url_for('admin.dashboard'))


# --- Teacher CRUD ---

@bp.route('/teacher/add', methods=['POST'])
@login_required
def add_teacher():
    name = request.form['name'].strip()
    if not name:
        flash('姓名不能为空', 'danger')
        return redirect(url_for('admin.dashboard'))
    if Teacher.query.filter_by(name=name).first():
        flash('老师已存在', 'danger')
        return redirect(url_for('admin.dashboard'))
    db.session.add(Teacher(name=name))
    db.session.commit()
    flash('老师添加成功', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/teacher/<int:tid>/delete', methods=['POST'])
@login_required
def delete_teacher(tid):
    teacher = Teacher.query.get_or_404(tid)
    db.session.delete(teacher)
    db.session.commit()
    flash('老师已删除', 'success')
    return redirect(url_for('admin.dashboard'))


# --- Tag CRUD ---

@bp.route('/tag/add', methods=['POST'])
@login_required
def add_tag():
    category = request.form['category'].strip()
    label = request.form['label'].strip()
    if not category or not label:
        flash('分类和标签不能为空', 'danger')
        return redirect(url_for('admin.dashboard'))
    db.session.add(Tag(category=category, label=label))
    db.session.commit()
    flash('标签添加成功', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/tag/<int:tid>/delete', methods=['POST'])
@login_required
def delete_tag(tid):
    tag = Tag.query.get_or_404(tid)
    db.session.delete(tag)
    db.session.commit()
    flash('标签已删除', 'success')
    return redirect(url_for('admin.dashboard'))


# --- Curriculum ---

@bp.route('/curriculum/add', methods=['POST'])
@login_required
def add_curriculum():
    course_id = request.form.get('course_id', type=int)
    year = request.form.get('year', type=int)
    student_type = request.form.get('student_type', '').strip()
    major_category = request.form.get('major_category', '').strip()
    sub_category = request.form.get('sub_category', '').strip()
    if not all([course_id, year, student_type, major_category, sub_category]):
        flash('请填写所有培养方案字段', 'danger')
        return redirect(url_for('admin.dashboard'))
    if student_type not in Config.STUDENT_TYPES:
        flash('学生类型无效', 'danger')
        return redirect(url_for('admin.dashboard'))
    if not CurriculumEntry.query.filter_by(course_id=course_id, year=year, student_type=student_type).first():
        db.session.add(CurriculumEntry(
            course_id=course_id, year=year, student_type=student_type,
            major_category=major_category, sub_category=sub_category,
        ))
        db.session.commit()
        flash('培养方案条目已添加', 'success')
    else:
        flash('该条目已存在', 'warning')
    return redirect(url_for('admin.dashboard'))


@bp.route('/curriculum/<int:cid>/delete', methods=['POST'])
@login_required
def delete_curriculum(cid):
    entry = CurriculumEntry.query.get_or_404(cid)
    db.session.delete(entry)
    db.session.commit()
    flash('已删除', 'success')
    return redirect(url_for('admin.dashboard'))


# --- Visitor Stats ---

@bp.route('/api/visitor_stats')
@login_required
def visitor_stats():
    days = min(request.args.get('days', 1, type=int), 30)
    since = datetime.utcnow() - timedelta(days=days)
    rows = (db.session.query(
        func.strftime('%Y-%m-%d %H:00', PageView.ts).label('hour'),
        func.count(PageView.ip.distinct()).label('cnt')
    ).filter(PageView.ts >= since).group_by('hour').order_by('hour').all())
    return jsonify([{'t': r.hour, 'n': r.cnt} for r in rows])


# --- Evaluation ---

@bp.route('/eval/<int:eid>/delete', methods=['POST'])
@login_required
def delete_eval(eid):
    ev = Evaluation.query.get_or_404(eid)
    db.session.delete(ev)
    db.session.commit()
    flash('评价已删除', 'success')
    return redirect(url_for('admin.dashboard'))
