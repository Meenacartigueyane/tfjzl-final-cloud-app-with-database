
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
import logging

from .models import Course, Enrollment, Question, Choice, Submission

logger = logging.getLogger(__name__)


# User Registration
def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        try:
            User.objects.get(username=username)
            context['message'] = "User already exists."
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        except User.DoesNotExist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")


# User Login
def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']

        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = "Invalid username or password."

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


# User Logout
def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


# Check Enrollment
def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()

    return False


# Course List View
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


# Course Detail View
class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


# Enroll in a Course
def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if user.is_authenticated:
        is_enrolled = check_if_enrolled(user, course)

        if not is_enrolled:
            Enrollment.objects.create(
                user=user,
                course=course,
                mode='honor'
            )

            course.total_enrollment += 1
            course.save()

    return HttpResponseRedirect(
        reverse(
            viewname='onlinecourse:course_details',
            args=(course.id,)
        )
    )


# Extract Answers from Exam Form
def extract_answers(request):
    submitted_answers = []

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                submitted_answers.append(int(value))
            except (ValueError, TypeError):
                continue

    return submitted_answers


# Submit Exam
def submit(request, course_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    if request.method != 'POST':
        return redirect(
            'onlinecourse:course_details',
            pk=course_id
        )

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    selected_answers = extract_answers(request)

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    valid_choices = Choice.objects.filter(
        question__course=course,
        id__in=selected_answers
    )

    submission.choices.set(valid_choices)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


# Show Exam Result
def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    selected_choice_ids = set(
        submission.choices.values_list('id', flat=True)
    )

    questions = Question.objects.filter(course=course)

    total_score = 0
    result_list = []

    for question in questions:
        question_choices = question.choice_set.all()

        correct_ids = set(
            question_choices.filter(
                is_correct=True
            ).values_list('id', flat=True)
        )

        all_choice_ids = set(
            question_choices.values_list('id', flat=True)
        )

        selected_ids = selected_choice_ids.intersection(
            all_choice_ids
        )

        is_correct = (
            bool(correct_ids) and correct_ids == selected_ids
        )

        if is_correct:
            total_score += question.grade

        result_list.append({
            'question': question,
            'is_correct': is_correct,
            'selected_choices': question_choices.filter(
                id__in=selected_ids
            ),
            'choices': question_choices
        })

    context = {
        'course': course,
        'grade': total_score,
        'submission': submission,
        'result_list': result_list,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
