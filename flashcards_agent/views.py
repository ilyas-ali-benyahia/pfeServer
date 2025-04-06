from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import agent, extract_flashcards_from_output, detect_language
import io
import sys
import contextlib

@api_view(["POST"])
def generate_flashcards(request):
    text = request.data.get("text", "")
    
    if not text:
        return Response({"error": "Text is required"}, status=400)
    
    # Detect language of the input text
    language = detect_language(text)
    
    # Capture the console output during agent execution
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        # Run the agent
        agent.invoke(text)
        
        # Get the console output
        agent_output = new_stdout.getvalue()
    finally:
        # Restore stdout
        sys.stdout = old_stdout
    
    # Extract flashcards from the output
    flashcards = extract_flashcards_from_output(agent_output)
    
    if not flashcards:
        # Fallback to a direct search if no flashcards were found in the observations
        import re
        
        if language == 'arabic':
            qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', agent_output, re.DOTALL)
            for question, answer in qa_pairs:
                flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
        else:
            qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', agent_output, re.DOTALL)
            for question, answer in qa_pairs:
                flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
    
    return Response({"flashcards": flashcards})