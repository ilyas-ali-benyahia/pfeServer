from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import quizzes_agent, extract_quizzes_from_output, detect_language
import io
import sys

@api_view(["POST"])
def generate_quizzes(request):
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
        # Create a system message that explicitly instructions the LLM to respond in Arabic if input is Arabic
        if language == 'arabic':
            # Add language instruction to the input
            input_with_instruction = f"""
            هام جداً: يجب أن تكون جميع الإجابات باللغة العربية فقط.
            
            النص المدخل:
            {text}
            """
            # Run the agent to generate quizzes with the instruction
            quizzes_agent.invoke(input_with_instruction)
        else:
            # Run the agent with original text for English
            quizzes_agent.invoke(text)
        
        # Extract the output from the system
        agent_output = new_stdout.getvalue()
    finally:
        # Restore stdout to normal
        sys.stdout = old_stdout
    
    # Extract quizzes from the output
    quizzes = extract_quizzes_from_output(agent_output)
    
    if not quizzes:
        # Fallback - direct generation if extraction failed
        import re
        from .utils import quiz_tool
        
        # Call quiz_tool directly to avoid agent overhead
        direct_output = quiz_tool(text)
        
        if language == 'arabic':
            # More flexible pattern for direct Arabic output
            quiz_pattern = r'س: (.*?)(?:\n|\r\n|\s+)(أ|أ\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(ب|ب\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(ج|ج\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(د|د\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(?:الإجابة الصحيحة:?|الجواب الصحيح:?)\s*([أ-د])'
            quiz_matches = re.findall(quiz_pattern, direct_output, re.DOTALL)
            
            for match in quiz_matches:
                question = match[0].strip()
                option_a = match[2].strip()
                option_b = match[4].strip()
                option_c = match[6].strip()
                option_d = match[8].strip()
                correct_answer = match[9].strip()
                
                quizzes.append({
                    "question": question,
                    "options": {
                        "أ": option_a,
                        "ب": option_b,
                        "ج": option_c,
                        "د": option_d
                    },
                    "correct_answer": correct_answer
                })
        else:
            # Direct extraction from the output for English
            quiz_pattern = r'Q: (.*?)\nA\. (.*?)\nB\. (.*?)\nC\. (.*?)\nD\. (.*?)\nCorrect Answer: ([A-D])'
            quiz_matches = re.findall(quiz_pattern, direct_output, re.DOTALL)
            
            for match in quiz_matches:
                question, option_a, option_b, option_c, option_d, correct_answer = map(str.strip, match)
                quizzes.append({
                    "question": question,
                    "options": {
                        "A": option_a,
                        "B": option_b,
                        "C": option_c,
                        "D": option_d
                    },
                    "correct_answer": correct_answer
                })
    
    if not quizzes:
        if language == 'arabic':
            error_message = "فشل في إنشاء الاختبارات"
        else:
            error_message = "Failed to generate quizzes"
        return Response({"error": error_message, "language": language}, status=500)
    
    return Response({"quizzes": quizzes})