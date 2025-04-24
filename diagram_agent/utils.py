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

# Define base URL for knowledge linking - this was missing in the original code
BASE_KNOWLEDGE_URL = "https://knowledge.example.com"

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
    }

def create_valid_url(text, base_url):
    """Create a valid URL from text content."""
    # Remove special characters and create URL-friendly slug
    slug = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    slug = re.sub(r'[\s-]+', '-', slug)
    
    # Ensure the slug is URL safe
    safe_slug = urllib.parse.quote(slug)
    
    # Return the full URL path
    return f"{base_url}/{safe_slug}"

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
            classDef feature fill:{color_palette['feature']},stroke:#333
            classDef benefit fill:{color_palette['benefit']},stroke:#333
            classDef technology fill:{color_palette['technology']},stroke:#333

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
            
            click A "https://knowledge.example.com/path" _blank
            click B "https://knowledge.example.com/path" _blank
            click D "https://knowledge.example.com/path" _blank
            
            ✅ **ملاحظات هامة:**
           - يجب أن تستخدم جميع الروابط **عناوين URL مطلقة** وتنتهي بـ `_blank`.
           - تأكد من أن URL يعمل بشكل صحيح.
           - تأكد من أشكال العقد وتنسيقها بشكل صحيح.
            """
        else:
            styling_instructions = f"""
            You must use exactly this diagram structure that works reliably:
            ```mermaid
            graph LR
            classDef feature fill:{color_palette['feature']},stroke:#69c,stroke-width:1px
            classDef benefit fill:{color_palette['benefit']},stroke:#6a6,stroke-width:1px
            classDef technology fill:{color_palette['technology']},stroke:#6c9,stroke-width:1px
            
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
            
            click A "https://knowledge.example.com/first-item" _blank
            click B "https://knowledge.example.com/subitem" _blank
            click D "https://knowledge.example.com/subitem" _blank
            
            ```
            
            ✅ **Important Notes:**
            - All links should use **absolute URLs** and end with `_blank`.
            - Ensure **proper node shapes and formatting**.
            - Make sure the URLs correctly relate to the node content.
            """

        # Generate instructions based on language
        if language == 'arabic':
            prompt = f"""
            أنشئ مخططًا دقيقًا لـ Mermaid استنادًا إلى وصف النص التالي:
            
            {input_text}
            
            {styling_instructions}
            
            🔹 **ملاحظات:** تأكد من أن المخطط يتبع **بالضبط** البنية الموضحة في التعليمات.
            ❌ **لا تضف أي تفسيرات، تعليقات، أو تعديلات إضافية** - فقط **كود Mermaid النقي**.
            🔗 **الروابط:** تأكد من أن كل رابط يرتبط منطقيًا بمحتوى العقدة التي يشير إليها.
            """
        else:
            prompt = f"""
            Create a precise Mermaid diagram based on the following text description:
            
            {input_text}
            
            {styling_instructions}
            
            🔹 **Notes:** Make sure the diagram follows **exactly** the structure shown in the instructions.
            ❌ **Do not include any prefixes, suffixes, or explanations** - just **pure Mermaid code**.
            🔗 **Links:** Ensure each link logically relates to the content of the node it references.
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
            diagram_code = "graph LR\n" + diagram_code
        
        # Ensure the diagram has styling if requested and not already present
        if include_colors and not any(["classDef" in diagram_code, "style" in diagram_code]):
            diagram_code = f"classDef feature fill:{color_palette['feature']},stroke:#69c,stroke-width:1px\n" + \
                           f"classDef benefit fill:{color_palette['benefit']},stroke:#6a6,stroke-width:1px\n" + \
                           f"classDef technology fill:{color_palette['technology']},stroke:#6c9,stroke-width:1px\n" + \
                           diagram_code
        
        # Add or fix click functionality if requested
        if include_clicks:
            # Extract all node IDs from the diagram
            nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)([^\]}\)]+)(?:\]|\)|\})', diagram_code)
            
            # Check if click lines already exist
            existing_clicks = set(re.findall(r'click\s+([A-Za-z0-9_]+)', diagram_code))
            
            # Remove any existing click lines to replace them with correct ones
            diagram_code = re.sub(r'click\s+[A-Za-z0-9_]+\s+"[^"]+"\s+_blank', '', diagram_code)
            
            # Add click lines for all nodes
            click_lines = []
            for node_id, node_text in nodes:
                # Clean text for URL slug and create a proper URL
                clean_text = re.sub(r'["<>]', '', node_text).strip()
                url = create_valid_url(clean_text, base_url)
                
                # Add click line with appropriate URL
                click_lines.append(f'click {node_id} "{url}" _blank')
            
            # Add the new click lines
            if click_lines:
                diagram_code += "\n\n" + "\n".join(click_lines)
        
        # Add RTL direction for Arabic if needed
        if language == 'arabic' and not any(["direction: RTL" in diagram_code, "direction:RTL" in diagram_code]):
            if any([diagram_code.startswith("graph "), diagram_code.startswith("flowchart ")]):
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
def extract_diagram_from_output(output_text):
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
            diagram_code = "graph LR\n" + diagram_code
        
        # Ensure class definitions are at the top
        class_defs = re.findall(r'(classDef [^\n]+)', diagram_code)
        if class_defs:
            for class_def in class_defs:
                diagram_code = diagram_code.replace(class_def, '')
            diagram_code = '\n'.join(class_defs) + '\n' + diagram_code.strip()
        
        # Fix any links
        click_lines = re.findall(r'(click [^\n]+)', diagram_code)
        for line in click_lines:
            diagram_code = diagram_code.replace(line, '')
        
        # Add proper click lines at the end
        node_lines = []
        nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)([^\]}\)]+)(?:\]|\)|\})', diagram_code)
        for node_id, node_text in nodes:
            # Clean text for URL slug and create a proper URL
            clean_text = re.sub(r'["<>]', '', node_text).strip()
            url = create_valid_url(clean_text, BASE_KNOWLEDGE_URL)
            node_lines.append(f'click {node_id} "{url}" _blank')
        
        if node_lines:
            diagram_code += '\n\n' + '\n'.join(node_lines)
        
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
            return match.group(1).strip()
    
    # Last resort
    code_blocks = re.findall(r'```(?:mermaid)?\s*([\s\S]*?)```', output_text)
    if code_blocks:
        return code_blocks[0].strip()
    
    logger.error("Failed to extract any diagram code")
    return None
