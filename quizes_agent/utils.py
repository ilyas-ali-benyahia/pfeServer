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

def quiz_tool(input_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Detect language
    language = detect_language(input_text)
    
    if language == 'arabic':
        # Arabic prompt with explicit instructions to respond in Arabic only
        prompt = """
        قم بإنشاء أسئلة اختبار متعددة الخيارات من النص التالي باللغة العربية فقط:
        
        {input_text}
        
        هام جداً: يجب أن تكون جميع الأسئلة والخيارات باللغة العربية حصراً.
        
        قم بإنشاء 5 أسئلة على الأقل. لكل سؤال، قم بتوفير 4 خيارات، واحد منها فقط صحيح.
        استخدم هذا التنسيق فقط:
        
        س: [اكتب السؤال هنا]
        أ. [الخيار الأول]
        ب. [الخيار الثاني]
        ج. [الخيار الثالث]
        د. [الخيار الرابع]
        الإجابة الصحيحة: [اكتب الحرف الصحيح هنا]
        
        لا تقم بإضافة أي محتوى أو تعليقات أخرى. يجب أن تكون الإجابة باللغة العربية حصراً.
        """
    else:  # Default to English
        prompt = """
        Create multiple-choice quiz questions from the following text:
        
        {input_text}
        
        Create at least 5 questions. For each question, provide 4 options with only one correct answer.
        Use only this format:
        
        Q: [Write the question here]
        A. [First option]
        B. [Second option]
        C. [Third option]
        D. [Fourth option]
        Correct Answer: [Write the correct letter here]
        
        Do not add any other content or comments.
        """
    
    # Set the generation_config with a higher temperature for more diverse output
    # and explicitly set the output language for Arabic text
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40
    }
    
    if language == 'arabic':
        generation_config["stop_sequences"] = ["Q:", "Question:"]
    
    response = model.generate_content(
        prompt.format(input_text=input_text),
        generation_config=generation_config
    )
    
    return response.text

# Define tool for LangChain agent with system instructions to respect the language
quiz_tool_obj = Tool(
    name="Quiz Generator",
    func=quiz_tool,
    description="Generates multiple-choice quiz questions from input text using Gemini in the same language as the input (Arabic or English). If the input is in Arabic, all output must be in Arabic."
)

# Initialize LangChain agent with Gemini
# For Arabic text, set a higher temperature to encourage more creative generation
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
quizzes_agent = initialize_agent(
    tools=[quiz_tool_obj],
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    memory=memory
)

def extract_quizzes_from_output(output_text):
    import re
    
    # Check if output contains Arabic question format
    if 'س:' in output_text and ('أ.' in output_text or 'أ:' in output_text):
        # Extract Arabic quiz questions from Observation sections
        observation_sections = re.findall(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
        
        all_quizzes = []
        for section in observation_sections:
            # Pattern to match Arabic quiz questions with flexible format
            quiz_pattern = r'س: (.*?)(?:\n|\r\n)(أ|أ\.)\.?\s*(.*?)(?:\n|\r\n)(ب|ب\.)\.?\s*(.*?)(?:\n|\r\n)(ج|ج\.)\.?\s*(.*?)(?:\n|\r\n)(د|د\.)\.?\s*(.*?)(?:\n|\r\n)الإجابة الصحيحة:?\s*([أ-د])'
            quizzes = re.findall(quiz_pattern, section, re.DOTALL)
            
            for quiz in quizzes:
                question = quiz[0].strip()
                option_a = quiz[2].strip()
                option_b = quiz[4].strip()
                option_c = quiz[6].strip()
                option_d = quiz[8].strip()
                correct_answer = quiz[9].strip()
                
                all_quizzes.append({
                    "question": question,
                    "options": {
                        "أ": option_a,
                        "ب": option_b,
                        "ج": option_c,
                        "د": option_d
                    },
                    "correct_answer": correct_answer
                })
        
        # If no matches found in observation sections, try the entire text with more flexible pattern
        if not all_quizzes:
            # More flexible pattern to match different formats that might appear
            quiz_pattern = r'س: (.*?)(?:\n|\r\n|\s+)(أ|أ\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(ب|ب\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(ج|ج\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(د|د\.)\.?\s*(.*?)(?:\n|\r\n|\s+)(?:الإجابة الصحيحة:?|الجواب الصحيح:?)\s*([أ-د])'
            quizzes = re.findall(quiz_pattern, output_text, re.DOTALL)
            
            for quiz in quizzes:
                question = quiz[0].strip()
                option_a = quiz[2].strip()
                option_b = quiz[4].strip()
                option_c = quiz[6].strip()
                option_d = quiz[8].strip()
                correct_answer = quiz[9].strip()
                
                all_quizzes.append({
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
        # Extract English quiz questions from Observation sections
        observation_sections = re.findall(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
        
        all_quizzes = []
        for section in observation_sections:
            # Pattern to match English quiz questions in the specified format
            quiz_pattern = r'Q: (.*?)\nA\. (.*?)\nB\. (.*?)\nC\. (.*?)\nD\. (.*?)\nCorrect Answer: ([A-D])'
            quizzes = re.findall(quiz_pattern, section, re.DOTALL)
            
            for quiz in quizzes:
                question, option_a, option_b, option_c, option_d, correct_answer = map(str.strip, quiz)
                all_quizzes.append({
                    "question": question,
                    "options": {
                        "A": option_a,
                        "B": option_b,
                        "C": option_c,
                        "D": option_d
                    },
                    "correct_answer": correct_answer
                })
        
        # If no matches found in observation sections, try the entire text
        if not all_quizzes:
            quiz_pattern = r'Q: (.*?)\nA\. (.*?)\nB\. (.*?)\nC\. (.*?)\nD\. (.*?)\nCorrect Answer: ([A-D])'
            quizzes = re.findall(quiz_pattern, output_text, re.DOTALL)
            
            for quiz in quizzes:
                question, option_a, option_b, option_c, option_d, correct_answer = map(str.strip, quiz)
                all_quizzes.append({
                    "question": question,
                    "options": {
                        "A": option_a,
                        "B": option_b,
                        "C": option_c,
                        "D": option_d
                    },
                    "correct_answer": correct_answer
                })
    
    return all_quizzes