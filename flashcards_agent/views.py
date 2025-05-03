from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import agent, extract_flashcards_from_output, detect_language, flashcard_tool
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
    
    # First approach: Try using the agent with output capturing
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        # Run the agent
        agent_result = agent.invoke(text)
        
        # Get the console output
        agent_output = new_stdout.getvalue()
    except Exception as e:
        # Log the error
        print(f"Agent error: {str(e)}")
        agent_output = ""
    finally:
        # Restore stdout
        sys.stdout = old_stdout
    
    # Extract flashcards from the output
    flashcards = extract_flashcards_from_output(agent_output)
    
    # If the agent approach failed, try direct tool approach as fallback
    if not flashcards:
        try:
            # Directly use the flashcard tool
            tool_output = flashcard_tool(text)
            
            # Process the direct tool output
            if language == 'arabic':
                import re
                qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', tool_output, re.DOTALL)
                for question, answer in qa_pairs:
                    flashcards.append({
                        "question": question.strip(),
                        "answer": answer.strip()
                    })
            else:
                import re
                qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', tool_output, re.DOTALL)
                for question, answer in qa_pairs:
                    flashcards.append({
                        "question": question.strip(),
                        "answer": answer.strip()
                    })
        except Exception as e:
            # Log the error
            print(f"Direct tool error: {str(e)}")
    
    # If we still have no flashcards, provide a meaningful error message
    if not flashcards:
        return Response({
            "error": "Failed to generate flashcards. Please try again with different text.",
            "flashcards": []
        }, status=200)  # Return 200 even on failure to make it easier for frontend
    
    return Response({"flashcards": flashcards})
