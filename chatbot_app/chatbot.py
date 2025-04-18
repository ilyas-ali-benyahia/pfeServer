import os
import cohere
from dotenv import load_dotenv
from typing import List, Optional
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from supabase import create_client, Client
import google.generativeai as genai
import jwt  # You'll need to install PyJWT

load_dotenv()

class GymChatbot:
    def setup_gemini_api(self):
    """
    Set up the Gemini API for text generation.
    """
    try:
        # Configure the Gemini API using your API key from environment variables
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.gemini_model = genai.GenerativeModel('gemini-pro')
    except Exception as e:
        print(f"Error setting up Gemini API: {e}")
        self.gemini_model = None

    def setup_cohere_api(self):
        """
        Set up the Cohere API for embeddings.
        """
        try:
            # Initialize the Cohere client for embeddings
            cohere_api_key = os.getenv("COHERE_API_KEY")
            self.co = cohere.Client(cohere_api_key)
        except Exception as e:
            print(f"Error setting up Cohere API: {e}")
            self.co = None
            
    def initialize_supabase(self):
        """
        Initialize the Supabase client.
        """
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            print(f"Error initializing Supabase: {e}")
            return None
    
    def embed_text(self, text, input_type="search_query"):
        """
        Generate embeddings for text using Cohere API.
        Works with multilingual text including Arabic.
        """
        try:
            if not self.co:
                print("Cohere client not initialized")
                return None
                
            # Generate embeddings
            response = self.co.embed(
                texts=[text],
                model="embed-multilingual-v3.0",
                input_type=input_type
            )
            # Return the embedding vector
            return response.embeddings[0]
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
        
    def get_user_from_token(self, token):
        """
        Extract user ID from a Supabase JWT token.
        """
        try:
            # Decode the JWT token
            decoded = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            # Extract the user ID
            user_id = decoded.get('sub')
            return user_id
        except Exception as e:
            print(f"Error decoding token: {e}")
            return None

    def delete_all_data(self, user_id=None):
        """
        Delete all records from Supabase for a specific user or all users.
        """
        try:
            if user_id:
                # Delete records only for this user
                self.supabase.table("chatbotcontent").delete().eq("user_id", user_id).execute()
                # Update user session status
                if user_id in self.user_sessions:
                    self.user_sessions[user_id] = False
            else:
                # Delete all records
                self.supabase.table("chatbotcontent").delete().neq("id", 0).execute()
                # Reset all user sessions
                self.user_sessions = {}
                self.is_initialized = False
        except Exception as e:
            print(f"Error deleting data: {e}")

    def process_text(self, text: str, user_id: str) -> bool:
        """
        Process text and create a vector store in Supabase for a specific user.
        Works with multilingual text including Arabic.
        """
        try:
            # Start fresh for this user
            self.delete_all_data(user_id)
            
            # Use langchain's CharacterTextSplitter which handles Unicode properly
            text_splitter = CharacterTextSplitter(
                chunk_size=self.chunk_size, 
                chunk_overlap=self.chunk_overlap,
                separator="\n"  # Use newlines as separators to respect Arabic text structure
            )
            split_texts = text_splitter.split_text(text)
            
            # Process each chunk
            for chunk in split_texts:
                # Ensure the text is properly encoded
                embedding = self.embed_text(chunk, input_type="search_document")
                if embedding:
                    self.supabase.table("chatbotcontent").insert({
                        "content": chunk,
                        "embedding": embedding,
                        "user_id": user_id  # Store the user ID
                    }).execute()
                    
            # Update user session status
            self.user_sessions[user_id] = True
            return True
        except Exception as e:
            print(f"Error processing text: {e}")
            return False

    def process_file(self, file_path: str, user_id: str) -> bool:
        """
        Process a file and create a vector store in Supabase for a specific user.
        Supports files with Arabic text.
        """
        try:
            # Use utf-8 encoding to properly handle Arabic characters
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()
            return self.process_text(text, user_id)
        except UnicodeDecodeError:
            # If utf-8 fails, try with another encoding common for Arabic
            try:
                with open(file_path, "r", encoding="cp1256") as file:  # Windows Arabic encoding
                    text = file.read()
                return self.process_text(text, user_id)
            except Exception as e:
                print(f"Error reading file with alternative encoding: {e}")
                return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False

    def retrieve_relevant_context(self, query: str, user_id: str, top_k: int = 6) -> List[str]:
        """
        Retrieve relevant context from Supabase for a specific user.
        Works with Arabic queries.
        """
        try:
            # Check if user has initialized data
            if user_id not in self.user_sessions or not self.user_sessions[user_id]:
                return []
                
            query_embedding = self.embed_text(query)
            if not query_embedding:
                return []

            # Use user_id in the RPC call
            response = self.supabase.rpc(
                'match_user_documents', 
                {
                    'query_embedding': query_embedding, 
                    'match_threshold': 0.1, 
                    'match_count': top_k,
                    'user_id_param': user_id  # Pass user_id to the SQL function
                }
            ).execute()

            return [row["content"] for row in response.data]
        except Exception as e:
            print(f"Error retrieving context: {e}")
            return []

    def generate_response(self, query: str, user_id: str) -> str:
    """
    Generate a response using Gemini for a specific user.
    Supports Arabic queries and responses.
    """
    try:
        # Check if user has initialized data
        if user_id not in self.user_sessions or not self.user_sessions[user_id]:
            # Check if query is in Arabic to respond accordingly
            if any('\u0600' <= c <= '\u06FF' for c in query):
                return "لم يتم تهيئة الروبوت المحادث بقاعدة معرفية بعد. يرجى تحميل النص أولاً."
            else:
                return "The chatbot has not been initialized with a knowledge base yet. Please upload text first."
            
        context = self.retrieve_relevant_context(query, user_id)
        if not context:
            # Check if query is in Arabic to respond accordingly
            if any('\u0600' <= c <= '\u06FF' for c in query):
                return "لم أتمكن من العثور على معلومات محددة. هل يمكنك إعادة صياغة سؤالك؟"
            else:
                return "I couldn't find specific information. Can you rephrase your question?"
        
        # Join the context
        context_text = "\n\n".join(context)
        
        # Create the prompt with the context and query
        prompt = f"""As an AI assistant, use the following information to answer the user's query.
        
        Information:
        {context_text}
        
        User's query: {query}
        
        Your response should be based on the provided information. If you don't know the answer, say so. If the user's query is in Arabic, respond in Arabic."""
        
        # Generate a response using Gemini
        if self.gemini_model:
            response = self.gemini_model.generate_content(prompt)
            return response.text
        else:
            # Fallback response
            if any('\u0600' <= c <= '\u06FF' for c in query):
                return "عذرًا، نواجه مشكلة في توليد الإجابة. يرجى المحاولة مرة أخرى لاحقًا."
            else:
                return "Sorry, we're experiencing an issue generating the response. Please try again later."
            
    except Exception as e:
        print(f"Error generating response: {e}")
        if any('\u0600' <= c <= '\u06FF' for c in query):  # Check if query is in Arabic
            return "حدث خطأ أثناء معالجة استفسارك."
        else:
            return "An error occurred while processing your query."
