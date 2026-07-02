from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from models import db, Course, Teacher, Evaluation, Tag, CurriculumEntry, PageView
from config import Config

bp = Blueprint('main', __name__)

_online = {}

@bp.before_request
def _track_online():
    ip = get_client_ip()
    now = datetime.utcnow()
    last = _online.get(ip)
    _online[ip] = now
    cutoff = now - timedelta(minutes=5)
    for k in [k for k, v in list(_online.items()) if v < cutoff]:
        del _online[k]
    if last is None or (now - last) >= timedelta(minutes=5):
        db.session.add(PageView(ip=ip, ts=now))
        db.session.commit()


def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()


@bp.route('/api/online')
def online_count():
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    return jsonify(count=sum(1 for v in _online.values() if v >= cutoff))


@bp.route('/')
def index():
    sel_year = request.args.get('year', type=int)
    sel_type = request.args.get('type', '').strip()

    all_courses = Course.query.order_by(Course.code).all()

    # 公共选修：不在任何培养方案且未被撤销的课程
    has_curriculum_ids = {
        r[0] for r in db.session.query(CurriculumEntry.course_id).distinct().all()
    }
    public_ids = {
        c.id for c in all_courses
        if c.id not in has_curriculum_ids and not c.exclude_from_public
    }

    grouped = None
    plan_ids = set()
    public_not_in_plan = []
    not_in_plan = []

    if sel_year and sel_type:
        entries = (CurriculumEntry.query
                   .filter_by(year=sel_year, student_type=sel_type)
                   .order_by(CurriculumEntry.sort_order)
                   .all())
        plan_ids = {e.course_id for e in entries}

        grouped = {}
        for e in entries:
            grouped.setdefault(e.major_category, {}).setdefault(e.sub_category, []).append(e)

        public_not_in_plan = [c for c in all_courses
                               if c.id not in plan_ids and c.id in public_ids]
        not_in_plan = [c for c in all_courses
                       if c.id not in plan_ids and c.id not in public_ids]

    available = (db.session.query(CurriculumEntry.year, CurriculumEntry.student_type)
                 .distinct().all())
    type_order = {t: i for i, t in enumerate(Config.STUDENT_TYPES)}
    available.sort(key=lambda x: (-x[0], type_order.get(x[1], 99)))

    eval_rows = (db.session.query(
        Evaluation.course_id, Evaluation.teacher_id, Evaluation.year,
        func.avg(Evaluation.rating).label('avg_r'),
        func.count(Evaluation.id).label('cnt')
    ).group_by(Evaluation.course_id, Evaluation.teacher_id, Evaluation.year).all())

    teacher_stats = {}
    unrated_counts = {}
    for r in eval_rows:
        if r.avg_r is None:
            key = (r.course_id, r.teacher_id)
            unrated_counts[key] = unrated_counts.get(key, 0) + r.cnt
            continue
        d = teacher_stats.setdefault(r.course_id, {}).setdefault(r.teacher_id, {'years': {}})
        d['years'][r.year] = (round(r.avg_r, 1), r.cnt)
    for cid, tmap in teacher_stats.items():
        for tid, data in tmap.items():
            yd = data['years']
            ry = max(yd)
            data['recent'] = {'year': ry, 'avg': yd[ry][0], 'cnt': yd[ry][1]}
            tc = sum(v[1] for v in yd.values())
            data['all'] = {'avg': round(sum(v[0]*v[1] for v in yd.values()) / tc, 1), 'cnt': tc}
    for (cid, tid), cnt in unrated_counts.items():
        if tid not in teacher_stats.get(cid, {}):
            teacher_stats.setdefault(cid, {})[tid] = {'all': {'avg': None, 'cnt': cnt}}

    sort = request.args.get('sort', '')
    sorted_pairs = []
    if sort == 'score':
        for course in all_courses:
            for t in course.teachers:
                s = teacher_stats.get(course.id, {}).get(t.id)
                if s and s['all']['avg'] is not None:
                    sorted_pairs.append({'course': course, 'teacher': t, 'stats': s,
                                         'in_plan': course.id in plan_ids or course.id in public_ids})
        sorted_pairs.sort(key=lambda x: (-x['stats']['all']['avg'], -x['stats']['all']['cnt']))

    available_years = sorted({r[0] for r in available}, reverse=True)
    available_types = [t for t in Config.STUDENT_TYPES if any(r[1] == t for r in available)]

    course_count = len(all_courses)
    rating_rows = db.session.query(Evaluation.rating, func.count(Evaluation.id)).group_by(Evaluation.rating).all()
    rating_dist = {r: 0 for r in range(1, 6)}
    for rating, cnt in rating_rows:
        rating_dist[rating] = cnt
    eval_count = sum(rating_dist.values())

    return render_template('index.html',
                           courses=all_courses,
                           sel_year=sel_year, sel_type=sel_type,
                           grouped=grouped, plan_ids=plan_ids,
                           public_ids=public_ids,
                           public_not_in_plan=public_not_in_plan,
                           not_in_plan=not_in_plan,
                           available=available,
                           available_years=available_years,
                           available_types=available_types,
                           teacher_stats=teacher_stats,
                           course_count=course_count,
                           eval_count=eval_count,
                           rating_dist=rating_dist,
                           sort=sort, sorted_pairs=sorted_pairs)


@bp.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    teacher_id = request.args.get('teacher_id', type=int)
    selected_teacher = None

    if teacher_id:
        selected_teacher = Teacher.query.get_or_404(teacher_id)
        if selected_teacher not in course.teachers:
            abort(404)

    evaluations = []
    already_submitted = False

    if selected_teacher:
        evaluations = (Evaluation.query
                       .filter_by(course_id=course_id, teacher_id=teacher_id)
                       .order_by(Evaluation.year.desc(), Evaluation.created_at.desc())
                       .all())
        ip = get_client_ip()
        year_submitted = {
            e.year for e in Evaluation.query.filter_by(
                course_id=course_id, teacher_id=teacher_id, submitter_ip=ip
            ).all()
        }
    else:
        year_submitted = set()

    tags = Tag.query.order_by(Tag.category, Tag.label).all()
    tag_groups = {}
    for t in tags:
        tag_groups.setdefault(t.category, []).append(t)

    return render_template('course.html',
                           course=course,
                           selected_teacher=selected_teacher,
                           evaluations=evaluations,
                           year_submitted=year_submitted,
                           tag_groups=tag_groups,
                           years=Config.YEARS)


@bp.route('/course/<int:course_id>/new_teacher_panel')
def new_teacher_panel(course_id):
    course = Course.query.get_or_404(course_id)
    return render_template('partials/add_teacher_panel.html', course=course)


@bp.route('/add_teacher', methods=['POST'])
def add_teacher():
    course_id = request.form.get('course_id', type=int)
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify(ok=False, msg='请输入老师姓名')
    course = Course.query.get_or_404(course_id)
    teacher = Teacher.query.filter_by(name=name).first()
    if not teacher:
        teacher = Teacher(name=name)
        db.session.add(teacher)
    if teacher not in course.teachers:
        course.teachers.append(teacher)
    db.session.commit()
    return jsonify(ok=True, course_id=course_id, teacher_id=teacher.id)

@bp.route('/course/<int:course_id>/teacher/<int:teacher_id>/stats')
def teacher_stats_api(course_id, teacher_id):
    rows = (db.session.query(Evaluation.year,
                             func.avg(Evaluation.rating).label('avg'),
                             func.count(Evaluation.id).label('cnt'))
            .filter_by(course_id=course_id, teacher_id=teacher_id)
            .filter(Evaluation.rating.isnot(None))
            .group_by(Evaluation.year).all())
    if not rows:
        return jsonify(avg=None, cnt=0)
    tc = sum(r.cnt for r in rows)
    return jsonify(avg=round(sum(r.avg * r.cnt for r in rows) / tc, 1), cnt=tc)


@bp.route('/course/<int:course_id>/teacher/<int:teacher_id>/panel')
def teacher_panel(course_id, teacher_id):
    course = Course.query.get_or_404(course_id)
    teacher = Teacher.query.get_or_404(teacher_id)
    if teacher not in course.teachers:
        abort(404)
    evaluations = (Evaluation.query
                   .filter_by(course_id=course_id, teacher_id=teacher_id)
                   .order_by(Evaluation.year.desc(), Evaluation.created_at.desc())
                   .all())
    ip = get_client_ip()
    year_submitted = set() if Config.ALLOW_MULTI_EVAL else {e.year for e in Evaluation.query.filter_by(
        course_id=course_id, teacher_id=teacher_id, submitter_ip=ip).all()}
    my_eval_ids = {e.id for e in evaluations if e.submitter_ip == ip}
    tags = Tag.query.order_by(Tag.category, Tag.label).all()
    tag_groups = {}
    for t in tags:
        tag_groups.setdefault(t.category, []).append(t)
    return render_template('partials/teacher_panel.html',
                           course=course, teacher=teacher,
                           evaluations=evaluations, year_submitted=year_submitted,
                           my_eval_ids=my_eval_ids,
                           tag_groups=tag_groups, years=Config.YEARS)


@bp.route('/evaluation/<int:eval_id>/delete', methods=['POST'])
def delete_evaluation(eval_id):
    ev = Evaluation.query.get_or_404(eval_id)
    if ev.submitter_ip != get_client_ip():
        abort(403)
    course_id, teacher_id = ev.course_id, ev.teacher_id
    db.session.delete(ev)
    db.session.commit()
    return jsonify(ok=True, course_id=course_id, teacher_id=teacher_id)


@bp.route('/submit', methods=['POST'])
def submit():
    course_id = request.form.get('course_id', type=int)
    teacher_id = request.form.get('teacher_id', type=int)
    year = request.form.get('year', type=int)
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    tag_ids = request.form.getlist('tags', type=int)

    course = Course.query.get_or_404(course_id)
    teacher = Teacher.query.get_or_404(teacher_id)

    if teacher not in course.teachers:
        abort(400)

    if (rating is not None and not (1 <= rating <= 5)) or year not in Config.YEARS:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(ok=False, msg='年份无效')
        flash('年份无效', 'danger')
        return redirect(url_for('main.course_detail', course_id=course_id, teacher_id=teacher_id))

    ip = get_client_ip()
    if not Config.ALLOW_MULTI_EVAL:
        exists = Evaluation.query.filter_by(
            course_id=course_id, teacher_id=teacher_id, year=year, submitter_ip=ip
        ).first()
        if exists:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(ok=False, msg='您已经提交过该学年的评价')
            flash('您已经提交过该学年的评价', 'warning')
            return redirect(url_for('main.course_detail', course_id=course_id, teacher_id=teacher_id))

    ev = Evaluation(course_id=course_id, teacher_id=teacher_id,
                    year=year, rating=rating, comment=comment or None,
                    submitter_ip=ip)
    if tag_ids:
        ev.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()

    db.session.add(ev)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(ok=True)
    flash('评价提交成功，感谢！', 'success')
    return redirect(url_for('main.course_detail', course_id=course_id, teacher_id=teacher_id))
