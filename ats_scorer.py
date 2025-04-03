from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

def calculate_ats_score(resume_json, job_description):
    """
    Calculate the ATS score between a resume and a job description.
    
    Args:
        resume_json (dict): Parsed resume data in JSON format.
        job_description (str or dict): Job description, either as a string or dictionary.
    
    Returns:
        float: ATS score as a percentage (0-100).
    """
    # Convert resume JSON to text
    resume_text = " ".join(
        f"{key}: {value}" for key, value in resume_json.items()
        if isinstance(value, str) or isinstance(value, list)
    )
    if isinstance(resume_json.get("experience"), list):
        resume_text += " " + " ".join(
            " ".join(f"{k}: {v}" for k, v in exp.items())
            for exp in resume_json["experience"]
        )
    if isinstance(resume_json.get("education"), list):
        resume_text += " " + " ".join(
            " ".join(f"{k}: {v}" for k, v in edu.items())
            for edu in resume_json["education"]
        )
    if isinstance(resume_json.get("skills"), list):
        resume_text += " " + " ".join(resume_json["skills"])

    # Ensure job_description is a dictionary
    if isinstance(job_description, str):  # If it's a string, convert to a dictionary
        job_description = {"Description": job_description}

    # Convert job description dict to text
    job_desc_text = " ".join(
        f"{key}: {value}" for key, value in job_description.items()
        if isinstance(value, str) or isinstance(value, list)
    )
    if isinstance(job_description.get("Education"), dict):
        job_desc_text += " " + " ".join(
            f"{k}: {v}" for k, v in job_description["Education"].items()
        )

    # Check for empty or insufficient input
    if not resume_text.strip() or not job_desc_text.strip():
        return 0  # Return 0% if either input is empty

    # Vectorize resume and job description
    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_desc_text])
        similarity = np.dot(tfidf_matrix[0], tfidf_matrix[1].T).toarray()[0][0]
        score = round(similarity * 100, 2)
        return max(0, min(100, score))  # Ensure score is within 0-100 range
    except ValueError as e:
        print(f"ATS Scoring Error: {e}")
        return 0