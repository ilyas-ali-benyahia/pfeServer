# BACKEND FIX - views.py

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import agent, extract_summary_from_output, detect_language, summary_tool
import io
import sys
import re

@api_view(["POST"])
def generate_summary(request):
    """Generates a summary and key points from the provided text.
    
    Fixed to ensure consistent naming and proper error handling.
    """
    text = request.data.get("text", "")
    
    if not text:
        return Response({"error": "Text is required"}, status=400)
    
    # Detect language of the input text
    language = detect_language(text)
    
    try:
        # Try direct tool call first for better reliability
        direct_result = summary_tool(text)
        results = extract_summary_from_output(direct_result)
        
        # If direct call didn't work well, try the agent approach
        if not results["summary"] and not results["key_points"]:
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
            
            # Extract summary and key points from the output
            results = extract_summary_from_output(agent_output)
        
        # Final fallback if still no results
        if not results["summary"] and not results["key_points"]:
            if language == 'arabic':
                # Arabic fallback patterns
                summary_match = re.search(r'ملخص.*?[:\n](.*?)(?=\n\n|$)', direct_result, re.DOTALL)
                if summary_match:
                    results["summary"] = summary_match.group(1).strip()
                
                # Look for bullet points or numbered items as key points
                key_points = re.findall(r'[•\-\*][\s]+([^\n]+)', direct_result)
                if key_points:
                    results["key_points"] = [point.strip() for point in key_points]
                else:
                    numbered_items = re.findall(r'\d+[\.:\-\s]+([^\n]+)', direct_result, re.DOTALL)
                    results["key_points"] = [item.strip() for item in numbered_items]
            else:
                # English fallback patterns
                summary_match = re.search(r'Summary.*?[:\n](.*?)(?=\n\n|$)', direct_result, re.DOTALL)
                if summary_match:
                    results["summary"] = summary_match.group(1).strip()
                else:
                    # Just take the first paragraph as summary if nothing else works
                    paragraphs = direct_result.split('\n\n')
                    if paragraphs:
                        results["summary"] = paragraphs[0].strip()
                
                # Look for bullet points or numbered items
                key_points = re.findall(r'[•\-\*][\s]+([^\n]+)', direct_result)
                if key_points:
                    results["key_points"] = [point.strip() for point in key_points]
                else:
                    numbered_items = re.findall(r'\d+[\.:\-\s]+([^\n]+)', direct_result, re.DOTALL)
                    results["key_points"] = [item.strip() for item in numbered_items]
        
        # Make sure we have at least some content
        if not results["summary"]:
            results["summary"] = "Summary generation failed. Please try again with different content."
        
        if not results["key_points"]:
            results["key_points"] = ["No key points identified."]
        
        return Response({
            "summary": results["summary"],
            "key_points": results["key_points"],
            "language": language
        })
        
    except Exception as e:
        error_message = "Failed to generate summary" if language != 'arabic' else "فشل في إنشاء الملخص"
        return Response({
            "error": f"{error_message}: {str(e)}",
            "summary": "",
            "key_points": [],
            "language": language
        }, status=500)