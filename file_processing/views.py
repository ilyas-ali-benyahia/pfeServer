import os
import re
import uuid
import base64
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from langchain.document_loaders import PyPDFLoader, UnstructuredFileLoader
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.formatters import TextFormatter
from supabase import create_client, Client
import tempfile
import magic
import pytesseract
from PIL import Image

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL1")
supabase_key = os.environ.get("SUPABASE_KEY1") 
supabase_bucket = os.environ.get("SUPABASE_BUCKET", "files")
supabase: Client = create_client(supabase_url, supabase_key)

def txt_to_text(txt_path):
    """
    Read text from a plain text file.
    
    Args:
        txt_path (str): Path to the text file
        
    Returns:
        str: Content of the text file
    """
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        # Try different encodings if UTF-8 fails
        try:
            with open(txt_path, 'r', encoding='latin-1') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Failed to read text file: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to read text file: {str(e)}")

# Function to extract text from images using OCR
def image_to_text(image_path):
    """
    Extract text from an image using Tesseract OCR.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Extracted text from the image
    """
    try:
        # Open the image using PIL
        img = Image.open(image_path)
        
        # Use pytesseract to do OCR on the image
        text = pytesseract.image_to_string(img)
        
        return text
    except Exception as e:
        raise Exception(f"OCR processing failed: {str(e)}")
   
def pptx_to_text(pptx_path):
    """Extract text from PowerPoint files"""
    # Using UnstructuredFileLoader
    loader = UnstructuredFileLoader(pptx_path)
    documents = loader.load()
    text = "\n\n".join([doc.page_content for doc in documents])
    
    return text

def docx_to_text(docx_path):
    """Extract text from Word documents"""
    # Using UnstructuredFileLoader
    loader = UnstructuredFileLoader(docx_path)
    documents = loader.load()
    text = "\n\n".join([doc.page_content for doc in documents])
    
    return text

@api_view(["POST"])
def upload_and_extract(request):
    """
    Handles either YouTube transcript extraction OR file uploads, not both.
    Returns extracted text based on the input (file or YouTube URL).
    """
    # Get YouTube URL or file from the request
    url = request.data.get("youtube_url", request.data.get("url", "")).strip()
    file = request.FILES.get("file", None)
    
    # Ensure only one input is provided (either file or YouTube URL)
    if url and file:
        return Response(
            {"error": "Please provide either a YouTube URL or a file, not both."},
            status=400,
        )
    
    # 🎬 Process YouTube URL if provided
    if url:
        # Improved regex to extract YouTube video ID from various URL formats
        regex = r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|\/|$)"
        video_id_match = re.search(regex, url)
        
        if not video_id_match:
            return Response({"error": "Invalid YouTube URL"}, status=400)
        
        video_id = video_id_match.group(1)
        
        try:
            # Try multiple language options - including Arabic
            languages_to_try = ['en', 'ar', 'es', 'fr', 'de']
            transcript = None
            
            # First try specific languages
            for lang in languages_to_try:
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    break
                except NoTranscriptFound:
                    continue
            
            # If specific languages failed, try to get any available transcript
            if not transcript:
                # Get list of available transcripts
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # First try to find an auto-generated transcript
                for t in transcript_list:
                    if t.is_generated:
                        transcript = t.fetch()
                        break
                
                # If no auto-generated transcript found, get the first available one
                if not transcript and len(list(transcript_list)) > 0:
                    transcript = list(transcript_list)[0].fetch()
            
            # If we still don't have a transcript, raise an error
            if not transcript:
                raise NoTranscriptFound(video_id, languages_to_try)
            
            # Extract the text from the transcript
            text = " ".join([item["text"] for item in transcript])
            
            return Response({
                "extracted_text": text
            })
        except TranscriptsDisabled:
            return Response({"error": "Transcripts are disabled for this YouTube video"}, status=400)
        except Exception as e:
            # Try to get available languages for better error message
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                available_language_codes = []
                
                for t in transcript_list:
                    if t.is_generated:
                        available_language_codes.append(f"{t.language_code} (auto-generated)")
                    else:
                        available_language_codes.append(t.language_code)
                
                language_options = ", ".join(available_language_codes)
                return Response({
                    "error": f"YouTube transcript extraction failed. Available languages: {language_options}",
                    "suggestion": "You may need to specify one of these languages in your request."
                }, status=400)
            except:
                return Response({"error": f"YouTube transcript extraction failed: {str(e)}"}, status=500)
    
    # 📂 Process file if provided
    if file:
        try:
            # Generate a unique filename to avoid collisions - REMOVED 'uploads/' prefix
            unique_filename = f"{uuid.uuid4()}-{file.name}"
            file_ext = file.name.split(".")[-1].lower()
            
            # Create a temporary file to process locally
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                for chunk in file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Get file mimetype
            mime_type = magic.Magic(mime=True).from_file(temp_file_path)
            
            # Upload file to Supabase
            with open(temp_file_path, 'rb') as f:
                file_content = f.read()
            
            # Simple test upload to debug Supabase connection
            try:
                # Upload to supabase storage
                supabase_response = supabase.storage.from_(supabase_bucket).upload(
                    unique_filename,
                    file_content,
                    {"content-type": mime_type}
                )
                
                # Get public URL (optional, depending on your bucket settings)
                file_url = supabase.storage.from_(supabase_bucket).get_public_url(unique_filename)
                
            except Exception as upload_error:
                # If upload fails, log the error but continue with text extraction
                print(f"Supabase upload error: {str(upload_error)}")
                file_url = None
            
            extracted_text = ""
            
            # Process the file based on its extension
            if file_ext == "pdf":
                loader = PyPDFLoader(temp_file_path)
                docs = loader.load()
                extracted_text = "\n".join([doc.page_content for doc in docs])
            elif file_ext == "docx":
                extracted_text = docx_to_text(temp_file_path)
            elif file_ext == "pptx":
                extracted_text = pptx_to_text(temp_file_path)
            elif file_ext in ["jpg", "jpeg", "png", "bmp", "tiff", "gif"]:
                extracted_text = image_to_text(temp_file_path)
            elif file_ext == "txt":
                extracted_text = txt_to_text(temp_file_path)
            else:
                # Clean up the temporary file
                os.unlink(temp_file_path)
                return Response(
                    {
                        "error": f"Unsupported file format: .{file_ext}",
                        "supported_formats": ["pdf", "docx", "pptx", "jpg", "jpeg", "png", "txt"],
                    },
                    status=400,
                )
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            # Check if text extraction was successful
            if not extracted_text.strip():
                return Response(
                    {
                        "error": "Text extraction failed. File might be empty or unreadable."
                    },
                    status=500,
                )
            
            # Return success response with extracted text and file info
            response_data = {
                "extracted_text": extracted_text
            }
            
            # Add file info if upload was successful
            if file_url:
                response_data["file_info"] = {
                    "filename": unique_filename,
                    "storage_path": unique_filename,
                    "file_url": file_url
                }
            
            return Response(response_data)
            
        except Exception as e:
            # Clean up the temporary file if it exists
            if 'temp_file_path' in locals():
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            return Response({"error": f"Text extraction failed: {str(e)}"}, status=500)
    
    # ❌ If neither YouTube URL nor file is provided
    return Response({"error": "No file or YouTube URL provided"}, status=400)

@api_view(["GET"])
def health_check(request):
    """
    Simple health check endpoint that returns 200 OK
    """
    return Response({"status": "ok"})