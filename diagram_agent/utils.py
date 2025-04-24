import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
import re
import logging
import langdetect
import random
import urllib.parse

# Set up logging to help with debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define a base URL for knowledge resources
BASE_KNOWLEDGE_URL = "https://example.com/knowledge"  # Change this to your actual base URL

def detect_language(text):
    """Detect if text is Arabic or English."""
    try:
        language = langdetect.detect(text)
        if language == 'ar':
            return 'arabic'
        else:
            return 'english'
    except:
        # Default to English if detection fails
        return 'english'

def get_color_palette():
    """Return a visually clear and consistent color palette."""
    return {
        "feature": "#4CAF50",   # Green (for features, growth, success)
        "benefit": "#FF9800",   # Orange (for benefits, attraction)
        "technology": "#2196F3", # Blue (for tech, innovation)
        "primary": "#3F51B5",   # Indigo (for main concepts)
        "secondary": "#9C27B0", # Purple (for supporting concepts)
    }

def create_valid_url_slug(text, base_url):
    """Create a valid URL slug from text."""
    # Remove non-alphanumeric characters
    slug = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    # Replace spaces with hyphens and make lowercase
    slug = slug.lower().replace(' ', '-')
    # Remove multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    # Trim hyphens from start and end
    slug = slug.strip('-')
    # Encode the URL properly
    encoded_slug = urllib.parse.quote(slug)
    # Create full URL
    return f"{base_url}/{encoded_slug}"

# Improved diagram tool function with working links and language support
def diagram_tool(input_text, include_colors=True, include_clicks=True, base_url=BASE_KNOWLEDGE_URL):
    try:
        # Detect language of the input text
        language = detect_language(input_text)
        logger.info(f"Diagram tool detected language: {language}")
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Generate a color palette
        color_palette = get_color_palette()
        
        # Create specific Mermaid diagram structure that works
        if language == 'arabic':
            styling_instructions = f"""
            يجب أن تستخدم هذا البناء الدقيق للمخطط:
             ```mermaid
            graph RL
            classDef feature fill:{color_palette['feature']},stroke:#333,color:white
            classDef benefit fill:{color_palette['benefit']},stroke:#333,color:white
            classDef technology fill:{color_palette['technology']},stroke:#333,color:white
            classDef primary fill:{color_palette['primary']},stroke:#333,color:white
            classDef secondary fill:{color_palette['secondary']},stroke:#333,color:white

            subgraph "العنوان الرئيسي"
            A["العنصر الأول"]:::feature
            
            subgraph "المجموعة الفرعية 1"
                B["العنصر الفرعي"]:::technology
            end
            subgraph "المجموعة الفرعية 2"
                D["العنصر الفرعي"]:::technology
            end
            A --> B
            A --> D
            D --> B
            D --> A
            end
            
            click A "{base_url}/item-1" _blank
            click B "{base_url}/item-2" _blank
            click D "{base_url}/item-3" _blank
            
            ✅ **ملاحظات هامة:**
           - يجب أن تستخدم جميع الروابط **عناوين URL مطلقة** وتنتهي بـ `_blank`.
           - تأكد من **أشكال العقد وتنسيقها بشكل صحيح**.
            """
        else:
            styling_instructions = f"""
            You must use exactly this diagram structure that works reliably:
            ```mermaid
            graph LR
            classDef feature fill:{color_palette['feature']},stroke:#333,color:white
            classDef benefit fill:{color_palette['benefit']},stroke:#333,color:white
            classDef technology fill:{color_palette['technology']},stroke:#333,color:white
            classDef primary fill:{color_palette['primary']},stroke:#333,color:white
            classDef secondary fill:{color_palette['secondary']},stroke:#333,color:white
            
            subgraph "Main Title"
            A["First Item"]:::feature
            
            subgraph "Subgroup 1"
                B["Subitem"]:::technology
            end
            subgraph "Subgroup 2"
                D["Subitem"]:::technology
            end
            A --> B
            A --> D
            D --> B
            D --> A
            end
            
            click A "{base_url}/first-item" _blank
            click B "{base_url}/subitem-1" _blank
            click D "{base_url}/subitem-2" _blank
            
            ```
            
            ✅ **Important Notes:**
            - All links should use **absolute URLs** and end with `_blank`.
            - Ensure **proper node shapes and formatting**.
            """

        # Generate instructions based on language
        if language == 'arabic':
            prompt = f"""
            أنشئ مخططًا دقيقًا لـ Mermaid استنادًا إلى وصف النص التالي:
            
            {input_text}
            
            {styling_instructions}
            
            🔹 **ملاحظات:** تأكد من أن المخطط يتبع **بالضبط** البنية الموضحة في التعليمات.
            ❌ **لا تضف أي تفسيرات، تعليقات، أو تعديلات إضافية** - فقط **كود Mermaid النقي**.
            """
        else:
            prompt = f"""
            Create a precise Mermaid diagram based on the following text description:
            
            {input_text}
            
            {styling_instructions}
            
            🔹 **Notes:** Make sure the diagram follows **exactly** the structure shown in the instructions.
            ❌ **Do not include any prefixes, suffixes, or explanations** - just **pure Mermaid code**.
            """

        # Set generation configuration based on language
        generation_config = {
            "temperature": 0.1,  # Lower temperature for more deterministic output
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048  # Ensure we get complete output
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Log the raw response for debugging
        logger.info(f"Raw Gemini response: {response.text}")
        
        # Process the response and clean up
        diagram_code = response.text.strip()
        
        # Remove markdown code blocks if present
        diagram_code = re.sub(r'```mermaid|```', '', diagram_code).strip()
        
        # Ensure diagram begins with 'graph' if missing
        if not any(diagram_code.startswith(prefix) for prefix in ['graph ', 'flowchart ']):
            if language == 'arabic':
                diagram_code = "graph RL\n" + diagram_code
            else:
                diagram_code = "graph LR\n" + diagram_code
        
        # Ensure the diagram has styling if requested and not already present
        if include_colors and not any(["classDef" in diagram_code]):
            color_defs = []
            for class_name, color in color_palette.items():
                color_defs.append(f"classDef {class_name} fill:{color},stroke:#333,color:white")
            diagram_code = "\n".join(color_defs) + "\n" + diagram_code
        
        # Extract all node IDs and text from the diagram
        nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)"?([^"\]}\)]+)"?(?:\]|\)|\})', diagram_code)
        
        # Remove existing click definitions
        diagram_code = re.sub(r'click\s+[A-Za-z0-9_]+\s+"[^"]*"\s+[^_]*_blank', '', diagram_code)
        
        # Add proper click functionality if requested
        if include_clicks and nodes:
            click_lines = []
            for node_id, node_text in nodes:
                # Create a valid URL for each node
                url = create_valid_url_slug(node_text, base_url)
                click_lines.append(f'click {node_id} "{url}" _blank')
            
            # Add the click lines at the end of the diagram
            diagram_code = diagram_code.strip() + "\n\n" + "\n".join(click_lines)
        
        # Add RTL direction for Arabic if needed
        if language == 'arabic' and "direction:" not in diagram_code:
            first_line_end = diagram_code.find("\n")
            if first_line_end != -1:
                diagram_code = diagram_code[:first_line_end] + " direction:RTL" + diagram_code[first_line_end:]
            else:
                diagram_code += " direction:RTL"
        
        return diagram_code
    except Exception as e:
        logger.error(f"Error in diagram tool: {str(e)}")
        return f"Error generating diagram: {str(e)}"

# Tool for generating diagrams using LangChain
diagram_tool_obj = Tool(
    name="Mermaid Diagram Generator",
    func=diagram_tool,
    description="Generates Mermaid diagrams from text descriptions using Gemini in the appropriate language (Arabic or English)."
)

# Initialize LangChain Agent
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2)

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

diagram_agent = initialize_agent(
    tools=[diagram_tool_obj],
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    memory=memory
)

# Extract function with fixes for links and language support
def extract_diagram_from_output(output_text, base_url=BASE_KNOWLEDGE_URL):
    logger.info(f"Agent output to extract from: {output_text}")
    
    # Detect language from the output
    language = detect_language(output_text)
    
    # Find diagram in output
    observation_match = re.search(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
    
    if observation_match:
        diagram_code = observation_match.group(1).strip()
        diagram_code = re.sub(r'```mermaid|```', '', diagram_code).strip()
        
        # Ensure diagram begins with 'graph' if missing
        if not any(diagram_code.startswith(prefix) for prefix in ['graph ', 'flowchart ']):
            if language == 'arabic':
                diagram_code = "graph RL\n" + diagram_code
            else:
                diagram_code = "graph LR\n" + diagram_code
        
        # Ensure class definitions are at the top
        class_defs = re.findall(r'(classDef [^\n]+)', diagram_code)
        if class_defs:
            for class_def in class_defs:
                diagram_code = diagram_code.replace(class_def, '')
            diagram_code = '\n'.join(class_defs) + '\n' + diagram_code.strip()
        
        # Extract all node IDs and texts
        nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)"?([^"\]}\)]+)"?(?:\]|\)|\})', diagram_code)
        
        # Remove existing click definitions
        diagram_code = re.sub(r'click\s+[A-Za-z0-9_]+\s+"[^"]*"\s+[^_]*_blank', '', diagram_code)
        
        # Add proper click lines at the end
        if nodes:
            click_lines = []
            for node_id, node_text in nodes:
                # Create a valid URL for the node
                url = create_valid_url_slug(node_text, base_url)
                click_lines.append(f'click {node_id} "{url}" _blank')
            
            # Add the click lines at the end of the diagram
            diagram_code = diagram_code.strip() + "\n\n" + "\n".join(click_lines)
        
        # Add RTL direction for Arabic if needed
        if language == 'arabic' and "direction:" not in diagram_code:
            first_line_end = diagram_code.find("\n")
            if first_line_end != -1:
                diagram_code = diagram_code[:first_line_end] + " direction:RTL" + diagram_code[first_line_end:]
            else:
                diagram_code += " direction:RTL"
        
        return diagram_code
    
    # Fallback patterns
    mermaid_patterns = [
        r'(graph [TBLR][DRLUD][\s\S]*?)(?=\n\n|$)',
        r'(sequenceDiagram[\s\S]*?)(?=\n\n|$)',
        r'(classDiagram[\s\S]*?)(?=\n\n|$)',
        r'(stateDiagram(?:-v2)?[\s\S]*?)(?=\n\n|$)',
        r'(gantt[\s\S]*?)(?=\n\n|$)',
        r'(pie[\s\S]*?)(?=\n\n|$)',
        r'(erDiagram[\s\S]*?)(?=\n\n|$)'
    ]
    
    for pattern in mermaid_patterns:
        match = re.search(pattern, output_text)
        if match:
            diagram_code = match.group(1).strip()
            
            # Apply the same click functionality as above
            nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)"?([^"\]}\)]+)"?(?:\]|\)|\})', diagram_code)
            diagram_code = re.sub(r'click\s+[A-Za-z0-9_]+\s+"[^"]*"\s+[^_]*_blank', '', diagram_code)
            
            if nodes:
                click_lines = []
                for node_id, node_text in nodes:
                    url = create_valid_url_slug(node_text, base_url)
                    click_lines.append(f'click {node_id} "{url}" _blank')
                diagram_code = diagram_code.strip() + "\n\n" + "\n".join(click_lines)
            
            return diagram_code
    
    # Last resort
    code_blocks = re.findall(r'```(?:mermaid)?\s*([\s\S]*?)```', output_text)
    if code_blocks:
        diagram_code = code_blocks[0].strip()
        
        # Apply the same click functionality
        nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)"?([^"\]}\)]+)"?(?:\]|\)|\})', diagram_code)
        diagram_code = re.sub(r'click\s+[A-Za-z0-9_]+\s+"[^"]*"\s+[^_]*_blank', '', diagram_code)
        
        if nodes:
            click_lines = []
            for node_id, node_text in nodes:
                url = create_valid_url_slug(node_text, base_url)
                click_lines.append(f'click {node_id} "{url}" _blank')
            diagram_code = diagram_code.strip() + "\n\n" + "\n".join(click_lines)
        
        return diagram_code
    
    logger.error("Failed to extract any diagram code")
    return None

# Function to render a diagram in HTML with interactive features
def render_interactive_diagram(diagram_code, diagram_id="mermaid-diagram"):
    """
    Renders a Mermaid diagram as interactive HTML
    """
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Interactive Mermaid Diagram</title>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10.0.2/dist/mermaid.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .diagram-container {{ 
                border: 1px solid #ccc; 
                padding: 20px;
                border-radius: 5px;
                background-color: #f9f9f9;
                overflow: auto;
            }}
            .node {{ cursor: pointer; }}
            .node:hover {{ opacity: 0.8; }}
        </style>
    </head>
    <body>
        <h1>Interactive Diagram</h1>
        <div class="diagram-container">
            <div id="{diagram_id}" class="mermaid">
                {diagram_code}
            </div>
        </div>
        
        <script>
            mermaid.initialize({{
                startOnLoad: true,
                securityLevel: 'loose',
                theme: 'default'
            }});
            
            // Add event listeners after rendering
            document.addEventListener('DOMContentLoaded', function() {{
                setTimeout(function() {{
                    // Add visual feedback on hover
                    const nodes = document.querySelectorAll('.node');
                    nodes.forEach(node => {{
                        node.style.cursor = 'pointer';
                        node.style.transition = 'transform 0.2s';
                        node.addEventListener('mouseover', function() {{
                            this.style.transform = 'scale(1.05)';
                        }});
                        node.addEventListener('mouseout', function() {{
                            this.style.transform = 'scale(1)';
                        }});
                    }});
                }}, 1000); // Give time for Mermaid to render
            }});
        </script>
    </body>
    </html>
    """
    return html_template

# Example usage function
def generate_and_display_diagram(description, output_format="mermaid"):
    """
    Generates and displays an interactive diagram from a text description
    
    Args:
        description: Text description of the diagram to generate
        output_format: 'mermaid' for raw code or 'html' for interactive HTML
    """
    # Get the agent's response
    agent_response = diagram_agent.run(f"Create a diagram for: {description}")
    
    # Extract the diagram code
    diagram_code = extract_diagram_from_output(agent_response)
    
    if not diagram_code:
        return "Failed to generate diagram."
    
    if output_format == "html":
        return render_interactive_diagram(diagram_code)
    else:
        return diagram_code
