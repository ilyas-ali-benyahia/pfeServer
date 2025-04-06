from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import (
    diagram_agent, 
    extract_diagram_from_output, 
    diagram_tool, 
    BASE_KNOWLEDGE_URL,
    detect_language
)
import io
import sys
import re
import logging

# Set up logging to help with debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@api_view(["POST"])
def generate_diagram(request):
    """
    API view to generate Mermaid diagrams from text descriptions.
    Automatically detects language (Arabic/English) and responds accordingly.
    """
    text = request.data.get("text", "")
    include_colors = request.data.get("include_colors", True)
    include_clicks = request.data.get("include_clicks", True)
    base_url = request.data.get("base_url", BASE_KNOWLEDGE_URL)
    
    if not text:
        # Return error response in appropriate language based on Accept-Language header
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
        if 'ar' in accept_language:
            return Response({"error": "النص مطلوب"}, status=400)
        else:
            return Response({"error": "Text description is required"}, status=400)
    
    # Detect language of the input text
    language = detect_language(text)
    logger.info(f"Detected language: {language}")
    
    # Capture the console output during agent execution
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        # Generate diagram with working links
        diagram_code = diagram_tool(
            text, 
            include_colors=include_colors,
            include_clicks=include_clicks, 
            base_url=base_url
        )
        
        # If direct tool call fails, try the agent
        if "Error generating diagram" in diagram_code:
            logger.info("Direct tool call failed, trying agent")
            
            # Create language-specific input
            if language == 'arabic':
                # Add specific instructions for Arabic output
                input_with_instruction = f"""
                مهم جداً: يجب أن تكون جميع النصوص في المخطط باللغة العربية.
                
                قم بإنشاء مخطط Mermaid من النص التالي:
                {text}
                """
                result = diagram_agent.invoke({"input": input_with_instruction})
            else:
                result = diagram_agent.invoke({"input": text})
            
            # Get the full agent output for debugging
            agent_output = new_stdout.getvalue()
            logger.debug(f"Full agent output: {agent_output}")
            
            if isinstance(result, dict) and 'output' in result:
                extracted_code = extract_diagram_from_output(result['output'], base_url=base_url)
                if extracted_code:
                    diagram_code = extracted_code
        
        # Fix any DOI links
        
        # Fix any DOI links that might still be present
        diagram_code = re.sub(r'click ([A-Za-z0-9_]+) "https://doi\.org[^"]*"', 
                             lambda m: f'click {m.group(1)} "{base_url}/{m.group(1).lower()}"', 
                             diagram_code)
        
        # Ensure all click lines use a working URL format
        lines = diagram_code.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('click '):
                if 'doi.org' in line or not ('http://' in line or 'https://' in line):
                    node_id = line.split(' ')[1]
                    lines[i] = f'click {node_id} "{base_url}/{node_id.lower()}" "Learn more"'
        
        diagram_code = '\n'.join(lines)
        
        return Response({
            "diagram_code": diagram_code,
            
        })
    
    except Exception as e:
        logger.exception(f"Error generating diagram: {str(e)}")
        return Response({
            "error": f"Error generating diagram: {str(e)}",
            "details": "Check server logs for more information"
        }, status=500)