from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Avg, Sum
from core.models import Domain, Topic, Question, UserProgress, MockExamResult, AdditionalTopic
from core.decorators import admin_required
from core.views import get_sidebar_data

# --- Student Management Views ---
@admin_required
def admin_dashboard_view(request):
    students = User.objects.filter(profile__role='student').order_by('username')
    student_list = []
    
    total_steps = 126  # 63 chapters * 2 (1 lesson + 1 quiz completed per chapter)
    
    for s in students:
        progress_qs = UserProgress.objects.filter(user=s)
        completed_lessons = progress_qs.filter(lesson_completed=True).count()
        completed_quizzes = progress_qs.filter(quiz_completed=True).count()
        
        # Calculate percentage progress
        total_completed = completed_lessons + completed_quizzes
        progress_percent = int(round((total_completed / total_steps) * 100)) if total_steps > 0 else 0
        
        # Quiz averages
        quiz_avg = progress_qs.filter(quiz_completed=True).aggregate(Avg('quiz_score'))['quiz_score__avg']
        quiz_avg = int(round(quiz_avg)) if quiz_avg is not None else 0
        
        # Mock exam scores
        mock_qs = MockExamResult.objects.filter(user=s).order_by('-date_taken')
        latest_mock = mock_qs.first()
        mock_count = mock_qs.count()
        mock_avg = mock_qs.aggregate(Avg('percentage'))['percentage__avg']
        mock_avg = int(round(mock_avg)) if mock_avg is not None else 0
        
        student_list.append({
            'user': s,
            'completed_lessons': completed_lessons,
            'completed_quizzes': completed_quizzes,
            'progress_percent': progress_percent,
            'quiz_avg': quiz_avg,
            'mock_count': mock_count,
            'mock_avg': mock_avg,
            'latest_mock': latest_mock
        })
        
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'students': student_list,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_dashboard',
    }
    return render(request, 'admin_panel/admin_dashboard.html', context)


@admin_required
def admin_create_student_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            email = request.POST.get('email')
            if email:
                user.email = email
                user.save()
                
            unlock_all = request.POST.get('unlock_all_topics') == 'true'
            allowed_topics_post = request.POST.getlist('allowed_topics')
            
            profile = user.profile
            profile.role = 'student'
            profile.unlock_all_topics = unlock_all
            profile.allowed_topics = [int(tid) for tid in allowed_topics_post if tid.isdigit()]
            profile.save()
            
            return redirect('admin_dashboard')
    else:
        form = UserCreationForm()
        
    domains = Domain.objects.prefetch_related('topics').all()
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'form': form,
        'domains': domains,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_dashboard',
        'is_edit': False
    }
    return render(request, 'admin_panel/admin_student_form.html', context)


@admin_required
def admin_edit_student_view(request, student_id):
    student = get_object_or_404(User, id=student_id, profile__role='student')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        new_pass = request.POST.get('new_password')
        
        unlock_all = request.POST.get('unlock_all_topics') == 'true'
        allowed_topics_post = request.POST.getlist('allowed_topics')
        
        if username:
            student.username = username
            student.email = email
            if new_pass:
                student.set_password(new_pass)
            student.save()
            
            profile = student.profile
            profile.unlock_all_topics = unlock_all
            profile.allowed_topics = [int(tid) for tid in allowed_topics_post if tid.isdigit()]
            profile.save()
            
            return redirect('admin_dashboard')
    
    domains = Domain.objects.prefetch_related('topics').all()
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'student': student,
        'domains': domains,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_dashboard',
        'is_edit': True
    }
    return render(request, 'admin_panel/admin_student_form.html', context)


@admin_required
def admin_delete_student_view(request, student_id):
    student = get_object_or_404(User, id=student_id, profile__role='student')
    if request.method == 'POST':
        student.delete()
        return redirect('admin_dashboard')
    
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'student': student,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_dashboard',
    }
    return render(request, 'admin_panel/admin_student_delete.html', context)


# --- Curriculum Management Views ---
# --- Platform Stats Views ---
@admin_required
def admin_stats_view(request):
    # Global metrics
    total_students = User.objects.filter(profile__role='student').count()
    
    # Progress
    total_steps = 126
    total_completed_steps = UserProgress.objects.filter(
        topic__id__range=(1, 63)
    ).aggregate(
        completed_lessons=Sum('lesson_completed'),
        completed_quizzes=Sum('quiz_completed')
    )
    
    comp_lessons = total_completed_steps['completed_lessons'] or 0
    comp_quizzes = total_completed_steps['completed_quizzes'] or 0
    
    avg_lessons = round(comp_lessons / total_students, 1) if total_students > 0 else 0
    avg_quizzes = round(comp_quizzes / total_students, 1) if total_students > 0 else 0
    
    overall_avg_progress = int(round(((comp_lessons + comp_quizzes) / (total_steps * total_students)) * 100)) if total_students > 0 else 0
    
    # Mock Exam results
    mocks = MockExamResult.objects.all()
    total_mocks_taken = mocks.count()
    
    avg_mock_score = mocks.aggregate(Avg('percentage'))['percentage__avg']
    avg_mock_score = int(round(avg_mock_score)) if avg_mock_score is not None else 0
    
    passing_mocks = mocks.filter(percentage__gte=82).count()
    mock_pass_rate = int(round((passing_mocks / total_mocks_taken) * 100)) if total_mocks_taken > 0 else 0
    
    # Hardest topics by quiz averages
    hardest_topics_qs = UserProgress.objects.filter(quiz_completed=True).values('topic__id', 'topic__title').annotate(avg_quiz=Avg('quiz_score')).order_by('avg_quiz')[:5]
    
    hardest_topics = []
    for item in hardest_topics_qs:
        hardest_topics.append({
            'id': item['topic__id'],
            'title': item['topic__title'],
            'avg_score': int(round(item['avg_quiz']))
        })
        
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'total_students': total_students,
        'avg_lessons': avg_lessons,
        'avg_quizzes': avg_quizzes,
        'overall_avg_progress': overall_avg_progress,
        'total_mocks_taken': total_mocks_taken,
        'avg_mock_score': avg_mock_score,
        'mock_pass_rate': mock_pass_rate,
        'hardest_topics': hardest_topics,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_stats',
    }
    return render(request, 'admin_panel/admin_stats.html', context)


@admin_required
def admin_board_view(request):
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_board',
    }
    return render(request, 'admin_panel/admin_board.html', context)


# --- Additional Topics Management Views ---

@admin_required
def admin_additional_topics_list_view(request):
    topics = AdditionalTopic.objects.all().order_by('created_at')
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'topics': topics,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_additional_topics',
    }
    return render(request, 'admin_panel/admin_additional_topics_list.html', context)


@admin_required
def admin_additional_topic_add_view(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        image1 = request.FILES.get('image1')
        image2 = request.FILES.get('image2')
        image3 = request.FILES.get('image3')

        if title and content:
            AdditionalTopic.objects.create(
                title=title,
                content=content,
                image1=image1,
                image2=image2,
                image3=image3
            )
            return redirect('admin_additional_topics')
        else:
            error_msg = "Title and Content are required."
    else:
        error_msg = None

    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'error_msg': error_msg,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_additional_topics',
        'is_edit': False
    }
    return render(request, 'admin_panel/admin_additional_topic_form.html', context)


@admin_required
def admin_additional_topic_edit_view(request, topic_id):
    topic = get_object_or_404(AdditionalTopic, id=topic_id)
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        
        # Check files
        if 'image1' in request.FILES:
            topic.image1 = request.FILES.get('image1')
        if 'image2' in request.FILES:
            topic.image2 = request.FILES.get('image2')
        if 'image3' in request.FILES:
            topic.image3 = request.FILES.get('image3')

        # Check for image deletions
        if request.POST.get('delete_image1') == 'true':
            topic.image1 = None
        if request.POST.get('delete_image2') == 'true':
            topic.image2 = None
        if request.POST.get('delete_image3') == 'true':
            topic.image3 = None

        if title and content:
            topic.title = title
            topic.content = content
            topic.save()
            return redirect('admin_additional_topics')
        else:
            error_msg = "Title and Content are required."
    else:
        error_msg = None

    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'topic': topic,
        'error_msg': error_msg,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_additional_topics',
        'is_edit': True
    }
    return render(request, 'admin_panel/admin_additional_topic_form.html', context)


@admin_required
def admin_additional_topic_delete_view(request, topic_id):
    topic = get_object_or_404(AdditionalTopic, id=topic_id)
    if request.method == 'POST':
        topic.delete()
        return redirect('admin_additional_topics')
        
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'topic': topic,
        'sidebar_domains': sidebar_domains,
        'active_page': 'admin_additional_topics',
    }
    return render(request, 'admin_panel/admin_additional_topic_delete.html', context)


