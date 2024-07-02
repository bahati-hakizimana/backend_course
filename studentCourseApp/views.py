from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from .models import StudentRegistration as Student
from .serializers import StudentSerializer
from courseApp.models import Course
from userApp.models import User
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import pandas as pd
import random

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def add_student(request):
    rol_no = request.data.get('rol_no')
    user = get_object_or_404(User, rol_no=rol_no)

    # Assign initial courses from level A
    level_a_courses = Course.objects.filter(level='A')[:4]
    if level_a_courses.count() < 4:
        return Response({'error': 'Not enough courses in level A to assign'}, status=400)

    students = []
    for course in level_a_courses:
        student = Student.objects.create(user=user, course=course)
        students.append(student)

    serializer = StudentSerializer(students, many=True)
    return Response(serializer.data, status=201)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .serializers import StudentSerializer
import random
from decimal import Decimal
from django.db.models import Avg

@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_student(request):
    rol_no = request.data.get('rol_no')
    course_code = request.data.get('course_code')
    marks = request.data.get('marks')

    if course_code is None or marks is None:
        return Response({'error': 'course_code and marks are required'}, status=400)

    course = get_object_or_404(Course, course_code=course_code)
    student = get_object_or_404(User, rol_no=rol_no)

    # Find the student's specific course enrollment(s)
    student_courses = Student.objects.filter(user=student, course=course)
    if not student_courses.exists():
        return Response({'error': 'Student is not enrolled in the specified course'}, status=400)

    # Update marks for all enrollments of the specific course
    for student_course in student_courses:
        student_course.marks = marks
        student_course.save()

    # Calculate total marks and 50% threshold
    total_marks = Decimal(course.total_marks)
    threshold = total_marks * Decimal('0.5')

    # Find all student's courses with less than 50% marks
    failed_courses = Student.objects.filter(user=student, marks__lt=threshold)
    
    # Ensure the student does not have more than 4 failed courses
    if failed_courses.count() > 4:
        # Sort the failed courses by level
        failed_courses_by_level = {}
        for fc in failed_courses:
            level = fc.course.level
            if level not in failed_courses_by_level:
                failed_courses_by_level[level] = []
            failed_courses_by_level[level].append(fc)

        # Remove failed courses until the student has no more than 4 failed courses
        while failed_courses.count() > 4:
            for level in sorted(failed_courses_by_level.keys(), reverse=True):
                if failed_courses_by_level[level]:
                    course_to_remove = failed_courses_by_level[level].pop()
                    course_to_remove.delete()
                    failed_courses = Student.objects.filter(user=student, marks__lt=threshold)
                    if failed_courses.count() <= 4:
                        break

    # Check if the student failed the current course
    if Decimal(marks) < threshold:
        # Re-assign the failed course
        Student.objects.create(user=student, course=course)
    else:
        # Check if the student has passed all courses in the current level
        current_level = course.level
        courses_in_current_level = Course.objects.filter(level=current_level)
        passed_all_courses_in_level = all(
            Student.objects.filter(user=student, course=course).exists() and
            Student.objects.filter(user=student, course=course).aggregate(marks_avg=Avg('marks'))['marks_avg'] >= (course.total_marks * Decimal('0.5'))
            for course in courses_in_current_level
        )

        if passed_all_courses_in_level:
            next_level = chr(ord(current_level) + 1)
            if next_level > 'D':  # No levels beyond D
                next_level = 'D'

            next_level_courses = Course.objects.filter(level=next_level).exclude(
                id__in=Student.objects.filter(user=student).values_list('course_id', flat=True)
            )

            if next_level_courses.count() > 0:
                new_course = random.choice(next_level_courses)
                if Student.objects.filter(user=student, course=new_course).count() < 4:
                    Student.objects.create(user=student, course=new_course)

    serializer = StudentSerializer(student_courses.first())
    return Response(serializer.data, status=200)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_courses(request, rol_no):
    user = get_object_or_404(User, rol_no=rol_no)
    students = user.student_set.all()
    serializer = StudentSerializer(students, many=True)
    return Response(serializer.data)



@api_view(['DELETE'])
def delete_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.delete()
    return Response(status=204)

@api_view(['GET'])
def find_all_students(request):
    students = Student.objects.all()
    serializer = StudentSerializer(students, many=True)
    return Response(serializer.data)

# studentCourseApp/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from userApp.models import User
from .serializers import UserSerializer

@api_view(['GET'])
def find_student_by_id(request, pk):
    user = get_object_or_404(StudentRegistration, pk=pk)
    serializer = StudentSerializer(user)
    return Response(serializer.data)




@api_view(['GET'])
def find_student_by_rol_no(request, rol_no):
    user = get_object_or_404(User, rol_no=rol_no)
    serializer = UserSerializer(user)
    return Response(serializer.data)



@api_view(['GET'])
def find_students_by_course(request, course_code):
    students = Student.objects.filter(course__course_code=course_code)
    serializer = StudentSerializer(students, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def find_students_by_marks(request, marks):
    students = Student.objects.filter(marks=marks)
    serializer = StudentSerializer(students, many=True)
    return Response(serializer.data)





@api_view(['GET'])
def download_all_students_pdf(request):
    students = Student.objects.all()

    response_pdf = HttpResponse(content_type='application/pdf')
    response_pdf['Content-Disposition'] = 'attachment; filename="all_students.pdf"'

    doc = SimpleDocTemplate(response_pdf, pagesize=letter)
    elements = []

    data = [['Roll No', 'Course', 'Marks', 'Created Date']]
    for student in students:
        data.append([
            student.user.rol_no,
            student.course.course_name,
            str(student.marks),
            student.created_date.strftime("%Y-%m-%d %H:%M:%S")
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)
    doc.build(elements)

    return response_pdf




@api_view(['GET'])
def download_all_students_excel(request):
    students = Student.objects.all()

    df = pd.DataFrame(list(students.values('user__rol_no', 'course__course_name', 'marks', 'created_date')))
    df.columns = ['Roll No', 'Course', 'Marks', 'Created Date']

    response_excel = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response_excel['Content-Disposition'] = 'attachment; filename="all_students.xlsx"'
    df.to_excel(response_excel, index=False)

    return response_excel





from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from .models import StudentRegistration
from userApp.models import User

@api_view(['GET'])
def download_student_pdf(request, rol_no):
    student = get_object_or_404(User, rol_no=rol_no)  # Assuming User model is used for student information

    response_pdf = HttpResponse(content_type='application/pdf')
    response_pdf['Content-Disposition'] = f'attachment; filename="{student.rol_no}_student.pdf"'

    doc = SimpleDocTemplate(response_pdf, pagesize=letter)
    elements = []

    # data = [['Roll No', 'Course', 'Marks', 'Created Date']]
    data = [['Course', 'Marks']]

    student_courses = StudentRegistration.objects.filter(user=student)
    for student_course in student_courses:
        data.append([
            # student.rol_no,
            student_course.course.course_name,
            str(student_course.marks),
            # student_course.created_date.strftime("%Y-%m-%d %H:%M:%S")
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)

    return response_pdf





@api_view(['GET'])
def download_student_excel(request, pk):
    student = get_object_or_404(Student, pk=pk)

    data = {
        'Roll No': [student.user.rol_no],
        'Course': [student.course.course_name],
        'Marks': [student.marks],
        'Created Date': [student.created_date.strftime("%Y-%m-%d %H:%M:%S")]
    }
    df = pd.DataFrame(data)

    response_excel = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response_excel['Content-Disposition'] = f'attachment; filename="{student.user.rol_no}_student.xlsx"'
    df.to_excel(response_excel, index=False)

    return response_excel