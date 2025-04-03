import google.generativeai as genai
import os
import json
import PyPDF2

# Configure API Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyBvURrD_5FENT2FdwODwFun8EbQ_7HBvYo"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Define the extraction prompt
EXTRACTION_PROMPT = '''Parse and extract the following fields from the uploaded resume:
1) Name
2) Email
3) Number
4) Education (as a list with subfields):
   a) School/college name
   b) Duration
   c) Course
   d) CGPA/Percentage
5) Skills (as a list)
6) Experience (as a list with subfields):
   a) Designation
   b) Organization name
   c) Project name
   d) Skills/concepts/technologies (as a list)
7) Certification (as a list with subfields):
   a) Name_certificate
   b) Issuer
8) Projects (as a list with subfields):
   c) Project name
   d) Skills/concepts/technologies (as a list)
Return the output in JSON format only, nothing else.
'''

def parse_resume_with_gemini(uploaded_file):
    """
    Parse a resume PDF using Gemini API and return extracted data in JSON format.
    Args:
        uploaded_file: Streamlit UploadedFile object (PDF)
    Returns:
        dict: Parsed resume data in JSON format
    """
    try:
        # Save file temporarily
        temp_file_path = "temp_resume.pdf"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        # Upload to Gemini API
        with open(temp_file_path, "rb") as file:
            gemini_file = genai.upload_file(file, display_name="Resume", mime_type="application/pdf")
        # Generate content synchronously
        response = model.generate_content([EXTRACTION_PROMPT, gemini_file])
        # Clean and parse the response
        response_text = response.text.strip("```json").strip("```").strip()
        try:
            extracted_data = json.loads(response_text)
            return extracted_data
        except json.JSONDecodeError as e:
            print(f"JSON Parsing Error: {e}")
            print(f"Raw Response: {response_text}")
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return {
                "name": "Unknown",
                "email": "Unknown",
                "number": "Unknown",
                "education": [],
                "skills": [skill.strip() for skill in text.split("Skills:")[-1].split("\n")[0].split(",")] if "Skills:" in text else [],
                "experience": [],
                "certification": [],
                "projects": []
            }
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)