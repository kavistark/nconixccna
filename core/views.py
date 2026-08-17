import re
import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Avg, Sum
from core.models import Domain, Topic, Question, UserProgress, MockExamResult
from core.decorators import admin_required

# --- Helper: Markdown to HTML Parser ---
def parse_markdown(text):
    if not text:
        return ""
    html = text
    
    # Headers
    html = re.sub(r'### (.*)', r'<h3>\1</h3>', html)
    html = re.sub(r'## (.*)', r'<h2>\1</h2>', html)
    html = re.sub(r'# (.*)', r'<h1>\1</h1>', html)
    
    # Code blocks
    html = re.sub(r'```cisco([\s\S]*?)```', r'<pre class="cisco-code">\1</pre>', html)
    html = re.sub(r'```([\s\S]*?)```', r'<pre>\1</pre>', html)
    html = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', html)
    
    # Bold / Italics
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
    
    # Blockquotes / Alerts
    html = re.sub(r'^> (.*)', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    # Images (Remap to static directory)
    html = re.sub(r'!\[([^\]]*)\]\(images/([^)]+)\)', r'<img src="/static/core/images/\2" alt="\1" class="lesson-image">', html)
    html = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" class="lesson-image">', html)
    
    # Tables
    lines = html.split('\n')
    in_table = False
    table_lines = []
    new_lines = []
    
    for line in lines:
        if line.strip().startswith('|'):
            in_table = True
            table_lines.append(line)
        else:
            if in_table:
                new_lines.append(process_table(table_lines))
                table_lines = []
                in_table = False
            new_lines.append(line)
    if in_table:
        new_lines.append(process_table(table_lines))
        
    html = '\n'.join(new_lines)
    return html

def process_table(lines):
    if len(lines) < 3:
        return '\n'.join(lines)
    
    headers = [cell.strip() for cell in lines[0].split('|')[1:-1]]
    
    table_html = '<table><thead><tr>'
    for h in headers:
        table_html += f'<th>{h}</th>'
    table_html += '</tr></thead><tbody>'
    
    for line in lines[2:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        table_html += '<tr>'
        for cell in cells:
            cell_fmt = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', cell)
            cell_fmt = re.sub(r'`([^`]+)`', r'<code>\1</code>', cell_fmt)
            table_html += f'<td>{cell_fmt}</td>'
        table_html += '</tr>'
        
    table_html += '</tbody></table>'
    return table_html


# --- Authentication Views ---
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')


# --- Context Processor helper to get domains and chapters for layout sidebar ---
def get_sidebar_data(user):
    domains = Domain.objects.prefetch_related('topics').all()
    # Map progress
    progress_map = {}
    if user.is_authenticated:
        user_progress = UserProgress.objects.filter(user=user)
        for up in user_progress:
            progress_map[up.topic_id] = {
                'lesson': up.lesson_completed,
                'quiz': up.quiz_completed
            }
            
    sidebar_domains = []
    for d in domains:
        topics_list = []
        for t in d.topics.all():
            prog = progress_map.get(t.id, {'lesson': False, 'quiz': False})
            
            # Check locking
            is_locked = True
            if user.is_authenticated:
                if user.is_superuser or user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'admin'):
                    is_locked = False
                elif hasattr(user, 'profile'):
                    is_locked = not user.profile.has_access_to_topic(t.id)
                else:
                    is_locked = False
            
            topics_list.append({
                'id': t.id,
                'title': t.title,
                'lesson_completed': prog['lesson'],
                'quiz_completed': prog['quiz'],
                'locked': is_locked
            })
        sidebar_domains.append({
            'name': d.name,
            'topics': topics_list
        })
    return sidebar_domains


# --- Core Views ---
@login_required
def dashboard_view(request):
    user = request.user
    if user.is_superuser or user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        return redirect('admin_dashboard')
    
    # Total Progress calculations (63 lessons + 63 quizzes = 126 total pages/steps)
    total_steps = 126
    
    progress_qs = UserProgress.objects.filter(user=user)
    completed_lessons = progress_qs.filter(lesson_completed=True).count()
    completed_quizzes = progress_qs.filter(quiz_completed=True).count()
    completed_steps = completed_lessons + completed_quizzes
    
    progress_percent = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
    
    # Quiz stats
    quizzes_taken = progress_qs.filter(quiz_completed=True).count()
    avg_score = progress_qs.filter(quiz_completed=True).aggregate(Avg('quiz_score'))['quiz_score__avg']
    avg_score = int(round(avg_score)) if avg_score is not None else 0
    
    # Domain Readiness Progression
    domains = Domain.objects.prefetch_related('topics').all()
    domain_readiness = []
    
    for d in domains:
        topic_ids = [t.id for t in d.topics.all()]
        total_domain_steps = len(topic_ids) * 2  # lesson + quiz
        
        domain_progress = progress_qs.filter(topic_id__in=topic_ids)
        completed_in_domain = (
            domain_progress.filter(lesson_completed=True).count() + 
            domain_progress.filter(quiz_completed=True).count()
        )
        
        domain_percentage = int((completed_in_domain / total_domain_steps) * 100) if total_domain_steps > 0 else 0
        
        domain_quizzes = domain_progress.filter(quiz_completed=True)
        domain_quiz_avg = domain_quizzes.aggregate(Avg('quiz_score'))['quiz_score__avg']
        domain_quiz_avg = int(round(domain_quiz_avg)) if domain_quiz_avg is not None else 0
        
        domain_readiness.append({
            'name': d.name,
            'progress_percent': domain_percentage,
            'completed_steps': completed_in_domain,
            'total_steps': total_domain_steps,
            'quiz_avg': domain_quiz_avg
        })

    # Sidebar data
    sidebar_domains = get_sidebar_data(user)

    # Calculate resume_id (first uncompleted unlocked lesson)
    resume_id = 1
    for i in range(1, 64):
        if hasattr(user, 'profile') and not user.profile.has_access_to_topic(i):
            continue
        up_topic = progress_qs.filter(topic_id=i).first()
        if not up_topic or not up_topic.lesson_completed:
            resume_id = i
            break

    context = {
        'progress_percent': progress_percent,
        'completed_steps': completed_steps,
        'total_steps': total_steps,
        'avg_score': avg_score,
        'quizzes_taken': quizzes_taken,
        'completed_lessons': completed_lessons,
        'domain_readiness': domain_readiness,
        'sidebar_domains': sidebar_domains,
        'resume_id': resume_id,
        'active_page': 'dashboard',
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def lesson_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    
    # Check access lock
    if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
        sidebar_domains = get_sidebar_data(request.user)
        return render(request, 'core/topic_locked.html', {
            'topic': topic,
            'sidebar_domains': sidebar_domains,
        })
        
    progress, _ = UserProgress.objects.get_or_create(user=request.user, topic=topic)
    
    parsed_lesson = parse_markdown(topic.lesson_content)
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'topic': topic,
        'current_topic_id': topic_id,
        'lesson_html': parsed_lesson,
        'progress': progress,
        'sidebar_domains': sidebar_domains,
        'active_page': 'lesson',
        'prev_id': topic_id - 1 if topic_id > 1 else None,
        'next_id': topic_id + 1 if topic_id < 63 else None,
    }
    return render(request, 'core/lesson.html', context)


@login_required
def lesson_complete_view(request, topic_id):
    if request.method == 'POST':
        # Check access lock
        if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
            return JsonResponse({'status': 'error', 'message': 'Access denied: Topic is locked.'}, status=403)
            
        topic = get_object_or_404(Topic, id=topic_id)
        progress, _ = UserProgress.objects.get_or_create(user=request.user, topic=topic)
        progress.lesson_completed = True
        progress.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)


@login_required
def quiz_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    
    # Check access lock
    if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
        sidebar_domains = get_sidebar_data(request.user)
        return render(request, 'core/topic_locked.html', {
            'topic': topic,
            'sidebar_domains': sidebar_domains,
        })
        
    questions = list(topic.questions.all())
    
    # We serialize questions to JSON so the slick client-side interactive card transitions remain identical
    serialized_questions = []
    for q in questions:
        serialized_questions.append({
            'question': q.question_text,
            'options': q.options,
            'correctIndex': q.correct_index,
            'explanation': q.explanation
        })
        
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'topic': topic,
        'current_topic_id': topic_id,
        'questions_json': json.dumps(serialized_questions),
        'sidebar_domains': sidebar_domains,
        'active_page': 'quiz',
    }
    return render(request, 'core/quiz.html', context)


@login_required
def quiz_submit_view(request, topic_id):
    if request.method == 'POST':
        # Check access lock
        if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
            return JsonResponse({'status': 'error', 'message': 'Access denied: Topic is locked.'}, status=403)
            
        data = json.loads(request.body)
        score = int(data.get('score', 0))
        
        topic = get_object_or_404(Topic, id=topic_id)
        progress, _ = UserProgress.objects.get_or_create(user=request.user, topic=topic)
        progress.quiz_completed = True
        # Keep highest score
        if score > progress.quiz_score:
            progress.quiz_score = score
        progress.save()
        
        return JsonResponse({'status': 'success', 'saved_score': progress.quiz_score})
    return JsonResponse({'status': 'invalid method'}, status=400)


@login_required
def mock_exam_setup_view(request):
    sidebar_domains = get_sidebar_data(request.user)
    return render(request, 'core/mock_exam_setup.html', {
        'sidebar_domains': sidebar_domains,
        'active_page': 'mock_exam',
    })


@login_required
def mock_exam_active_view(request):
    # Determine test size from GET parameter
    size = int(request.GET.get('size', 15))
    if size not in [15, 30, 60]:
        size = 15
        
    # Get questions restricted to allowed topics (unless admin)
    user = request.user
    if user.is_superuser or user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        all_questions = list(Question.objects.select_related('topic').all())
    elif hasattr(user, 'profile'):
        profile = user.profile
        if profile.unlock_all_topics:
            all_questions = list(Question.objects.select_related('topic').all())
        else:
            all_questions = list(Question.objects.filter(topic_id__in=profile.allowed_topics).select_related('topic').all())
            # Fallback if student doesn't have enough unlocked topics
            if len(all_questions) < size:
                all_questions = list(Question.objects.select_related('topic').all())
    else:
        all_questions = list(Question.objects.select_related('topic').all())
        
    if len(all_questions) == 0:
        return redirect('mock_exam_setup')
        
    # Shuffle and select a subset
    random.shuffle(all_questions)
    selected_questions = all_questions[:size]
    
    # Store selected questions in session to validate answers on submit
    session_questions = []
    for q in selected_questions:
        session_questions.append({
            'id': q.id,
            'question': q.question_text,
            'options': q.options,
            'correctIndex': q.correct_index,
            'explanation': q.explanation,
            'topicId': q.topic.id,
            'topicTitle': q.topic.title
        })
    
    request.session['active_mock_exam'] = session_questions
    
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'questions_json': json.dumps(session_questions),
        'seconds_remaining': size * 90,  # 1.5 min per question
        'sidebar_domains': sidebar_domains,
        'active_page': 'mock_exam',
    }
    return render(request, 'core/mock_exam_active.html', context)


@login_required
def mock_exam_submit_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_answers = data.get('answers', [])
        
        session_exam = request.session.get('active_mock_exam')
        if not session_exam:
            return JsonResponse({'status': 'error', 'message': 'No active exam session found'}, status=400)
            
        # Calculate scores
        correct_count = 0
        breakdown = []
        
        for idx, q in enumerate(session_exam):
            user_ans = user_answers[idx] if idx < len(user_answers) else None
            is_correct = (user_ans == q['correctIndex'])
            if is_correct:
                correct_count += 1
                
            breakdown.append({
                'topicId': q['topicId'],
                'topicTitle': q['topicTitle'],
                'question': q['question'],
                'options': q['options'],
                'userAnswer': user_ans,
                'correctIndex': q['correctIndex'],
                'isCorrect': is_correct,
                'explanation': q['explanation']
            })
            
        percent = int(round((correct_count / len(session_exam)) * 100))
        
        # Save to MockExamResult model
        MockExamResult.objects.create(
            user=request.user,
            total_questions=len(session_exam),
            correct_answers=correct_count,
            percentage=percent
        )
        
        # Clear session active exam
        if 'active_mock_exam' in request.session:
            del request.session['active_mock_exam']
            
        return JsonResponse({
            'status': 'success',
            'percentage': percent,
            'correct_count': correct_count,
            'total_questions': len(session_exam),
            'breakdown': breakdown
        })
        
    return JsonResponse({'status': 'invalid method'}, status=400)


