import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
import langdetect

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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

def flashcard_tool(input_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Detect language
    language = detect_language(input_text)
    
    if language == 'arabic':
        prompt = """
        قم بإنشاء بطاقات تعليمية من النص التالي:
        
        {input_text}
        
        أعد فقط البطاقات التعليمية بهذا التنسيق:
        س: سؤال
        ج: جواب
        
        قم بإنشاء 5 بطاقات تعليمية على الأقل. لا تقم بتضمين أي نص أو أفكار أو شروحات إضافية.
        """
    else:  # Default to English
        prompt = """
        Generate flashcards from the following text:
        
        {input_text}
        
        Return ONLY the flashcards in this format:
        Q: question
        A: answer
        
        Generate at least 5 flashcards. Do not include any additional text, thoughts, or explanations.
        """
    
    response = model.generate_content(prompt.format(input_text=input_text))
    return response.text

# Define tool for LangChain agent
flashcard_tool_obj = Tool(
    name="Flashcard Generator",
    func=flashcard_tool,
    description="Generates flashcards from input text using Gemini in the appropriate language (Arabic or English)."
)

# Initialize LangChain agent with Gemini
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = initialize_agent(
    tools=[flashcard_tool_obj],
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,  # You can set this to False later
    memory=memory
)

# Create a function to extract flashcards from agent output
def extract_flashcards_from_output(output_text):
    import re
    
    # Check if output contains Arabic question/answer format
    if 'س:' in output_text and 'ج:' in output_text:
        # This pattern captures the Arabic Q&A pairs from the Observation sections
        observation_sections = re.findall(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
        
        all_flashcards = []
        for section in observation_sections:
            # Extract Arabic Q&A pairs from each observation section
            qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', section, re.DOTALL)
            for question, answer in qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
                
        # If no matches found in observation sections, try the entire text
        if not all_flashcards:
            qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', output_text, re.DOTALL)
            for question, answer in qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
    else:
        # This pattern captures the English Q&A pairs from the Observation sections
        observation_sections = re.findall(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
        
        all_flashcards = []
        for section in observation_sections:
            # Extract English Q&A pairs from each observation section
            qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', section, re.DOTALL)
            for question, answer in qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
                
        # If no matches found in observation sections, try the entire text
        if not all_flashcards:
            qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', output_text, re.DOTALL)
            for question, answer in qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
    
    return all_flashcards