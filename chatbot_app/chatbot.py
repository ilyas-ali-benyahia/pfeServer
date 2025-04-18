import os
import re
from typing import List, Optional
from langchain.text_splitter import CharacterTextSplitter
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class GymChatbot:
    def __init__(self):
        """
        Initialize the chatbot without database or embeddings.
        """
        self.setup_gemini_api()
        self.is_initialized = False
        self.chunk_size = 1200
        self.chunk_overlap = 100
        self.knowledge_base = []  # Store text chunks in memory

    def setup_gemini_api(self):
        """
        Set up Google Gemini API configuration.
        """
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.model = genai.GenerativeModel(model_name="gemini-1.5-pro")
        except Exception as e:
            print(f"Error setting up Gemini API: {e}")
            raise

    def delete_all_data(self):
        """
        Clear all stored knowledge.
        """
        self.knowledge_base = []
        self.is_initialized = False

    def process_text(self, text: str) -> bool:
        """
        Process text and store in memory instead of Supabase.
        Works with multilingual text including Arabic.
        """
        try:
            # Start fresh
            self.delete_all_data()
            
            # Use langchain's CharacterTextSplitter which handles Unicode properly
            text_splitter = CharacterTextSplitter(
                chunk_size=self.chunk_size, 
                chunk_overlap=self.chunk_overlap,
                separator="\n"  # Use newlines as separators to respect Arabic text structure
            )
            split_texts = text_splitter.split_text(text)
            
            # Store chunks directly in memory
            self.knowledge_base = split_texts
                    
            self.is_initialized = True
            return True
        except Exception as e:
            print(f"Error processing text: {e}")
            return False

    def process_file(self, file_path: str) -> bool:
        """
        Process a file and store in memory.
        Supports files with Arabic text.
        """
        try:
            # Use utf-8 encoding to properly handle Arabic characters
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()
            return self.process_text(text)
        except UnicodeDecodeError:
            # If utf-8 fails, try with another encoding common for Arabic
            try:
                with open(file_path, "r", encoding="cp1256") as file:  # Windows Arabic encoding
                    text = file.read()
                return self.process_text(text)
            except Exception as e:
                print(f"Error reading file with alternative encoding: {e}")
                return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False

    def generate_response(self, query: str) -> str:
        """
        Generate a response using Gemini by sending all context directly.
        Supports Arabic queries and responses.
        """
        try:
            if not self.is_initialized or not self.knowledge_base:
                # Detect language for appropriate response
                is_arabic = any('\u0600' <= c <= '\u06FF' for c in query)
                if is_arabic:
                    return "he chatbot hasn't been initialized with a knowledge base yet. Please upload text first."
                else:
                    return "The chatbot hasn't been initialized with a knowledge base yet. Please upload text first."
            
            # Detect if the query is in Arabic to respond in the same language
            is_arabic = any('\u0600' <= c <= '\u06FF' for c in query)
            
            # Combine all knowledge base text into context
            context = "\n\n".join(self.knowledge_base)
            
            if is_arabic:
                prompt = f"""
                أنت مساعد خبير في صالة الألعاب الرياضية. استخدم السياق التالي للإجابة على الاستفسار:

                السياق:
                {context}

                استفسار المستخدم: {query}
                
                أجب فقط بناءً على السياق المقدم. إذا لم يكن لديك معلومات كافية، فأخبر بذلك.
                """
            else:
                prompt = f"""
                You are an expert gym assistant. Use the following context to answer the query:

                Context:
                {context}

                User Query: {query}
                
                Answer based only on the provided context. If you don't have enough information, say so.
                """
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
        
        except Exception as e:
            print(f"Error generating response: {e}")
            if any('\u0600' <= c <= '\u06FF' for c in query):  # Check if query is in Arabic
                return "An error occurred while processing your query."
            else:
                return "An error occurred while processing your query."
