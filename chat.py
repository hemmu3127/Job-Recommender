# chat.py
import google.generativeai as genai
import os
import json

def chat_with_gemini(resume_json, job_desc, user_input, chat_history=None):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyBvURrD_5FENT2FdwODwFun8EbQ_7HBvYo"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    if chat_history is None:
        chat_history = []
    prompt = (
        f"Resume: {json.dumps(resume_json)}\n"
        f"Job Description: {job_desc}\n"
        f"Chat History:\n"
    )
    for entry in chat_history:
        prompt += f"User: {entry['user']}\nAI: {entry['ai']}\n"
    prompt += f"User Question: {user_input}\nProvide suggestions or answers in context of the above. but give the answers precisely for the question asked"
    response = model.generate_content(prompt)
    return response.text