# Copyright 2018 Google LLC
# Copyright 2024 CESAR.School
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
#
# This code was based and contains a modifyed version of Google QuickStart guide 
# from: https://github.com/googleworkspace/python-samples/tree/main/docs/quickstart
# 

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly"]


def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        # Call the Classroom API
        service = build("classroom", "v1", credentials=creds)


        classroom_id = '' # Change to the id of the classroom you want to access
        coursework_id = '' # Change to the id of the work you want to access

        #results = service.courses().list().execute()
        #courses = results.get("courses", [])
        #students = service.courses().students().list(courseId=classroom_id).execute()
        #assignments = service.courses().courseWork().list(courseId=classroom_id).execute()
        submissions = service.courses().courseWork().studentSubmissions().list(courseId=classroom_id, courseWorkId=coursework_id).execute()


        """if not courses:
            print("No courses found.")
        else:
            print("Courses:")
            for course in courses:
                print(f"{course['name']}: {course['id']}")"""

        """for student in students.get('students', []):
            if 'profile' in student and 'emailAddress' in student['profile']:
                print(f"{student['profile']['name']['fullName']} - {student['profile']['emailAddress']} - {extract_prefix(student['profile']['emailAddress'])}")
            else:
                print(f"Email address not found for student: {student['profile']['name']['fullName']}")"""
      
        """for assignment in assignments.get('courseWork', []):
            print(f"{assignment['title']} - ID: {assignment['id']}")"""
        
      
        open("ErroFormatacao.txt", "w")
        for submission in submissions.get('studentSubmissions', []):
            student_id = submission['userId']
            student = service.courses().students().get(courseId=classroom_id, userId=student_id).execute()

            student_name = student['profile']['name']['fullName']
            student_email = student['profile']['emailAddress']
            student_login = extract_prefix(student_email)
            late = submission.get('late', False)
            missing = submission.get('missing', False)
            attachments = submission.get('assignmentSubmission', {}).get('attachments', [])

            print("Student Name:", student_name)
            print("Student Email:", student_email)
            print("Student Login:", student_login)
            print("Late:", late)
            print("Missing:", missing)

            with open("ErroFormatacao.txt", "a") as file:
                print("Attachments:")
                if attachments:
                    if len(attachments) > 1:
                        file.write(f"{student_name} - Entregou mais de um arquivo\n")
                    else:
                        for attachment in attachments:
                            file_name = attachment.get('driveFile', {}).get('title', 'No file name')
                            print("  File Name:", file_name)

                            if '.zip' not in file_name:
                                file.write(f"{student_name} - Não entregou .zip\n")
                            
                            elif file_name != student_login + '.zip':
                                file.write(f"{student_name} - Arquivo com nome errado - Nome corrigido: {student_login + '.zip'}\n")
                else:
                    print("  No attachments found")
                    file.write(f"{student_name} - Nenhum arquivo encontrado\n")
                print()
          
    except HttpError as error:
      if error.resp.status == 404:
          print("Course not found. Please check if the provided classroom ID is correct.")
      else:
          print(f"An error occurred: {error}")

    print("DONE")

def extract_prefix(s):
    parts = s.split('@')
    return parts[0]

if __name__ == "__main__":
    main()
