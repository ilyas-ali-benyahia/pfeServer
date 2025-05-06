import os
import re
import uuid
import base64
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from langchain.document_loaders import PyPDFLoader
from langchain_community.document_loaders import UnstructuredFileLoader  # corrected import
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from supabase import create_client, Client
import tempfile
import mimetypes
import pytesseract
from PIL import Image
import dotenv

dotenv.load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_bucket = os.getenv("SUPABASE_BUCKET", "files")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase credentials not found in environment variables")

supabase: Client = create_client(supabase_url, supabase_key)

def txt_to_text(txt_path):
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        try:
            with open(txt_path, 'r', encoding='latin-1') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Failed to read text file: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to read text file: {str(e)}")

def image_to_text(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        raise Exception(f"OCR processing failed: {str(e)}")

def pptx_to_text(pptx_path):
    loader = UnstructuredFileLoader(pptx_path)
    documents = loader.load()
    return "\n\n".join([doc.page_content for doc in documents])

def docx_to_text(docx_path):
    loader = UnstructuredFileLoader(docx_path)
    documents = loader.load()
    return "\n\n".join([doc.page_content for doc in documents])

def sanitize_filename(filename):
    sanitized = re.sub(r'[\s\[\]\(\)\{\}]', '_', filename)
    sanitized = re.sub(r'[^\w\-\.]', '', sanitized)
    return sanitized

@api_view(["POST"])
def upload_and_extract(request):
    url = request.data.get("youtube_url", request.data.get("url", "")).strip()
    file = request.FILES.get("file", None)

    if url and file:
        return Response({"error": "Please provide either a YouTube URL or a file, not both."}, status=400)

    if url:
        regex = r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|\/|$)"
        match = re.search(regex, url)
        if not match:
            return Response({"error": "Invalid YouTube URL"}, status=400)
        video_id = match.group(1)

        try:
            languages_to_try = ['en', 'ar', 'es', 'fr', 'de']
            transcript = None
            for lang in languages_to_try:
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    break
                except NoTranscriptFound:
                    continue
            if not transcript:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                for t in transcript_list:
                    if t.is_generated:
                        transcript = t.fetch()
                        break
                if not transcript and len(list(transcript_list)) > 0:
                    transcript = list(transcript_list)[0].fetch()
            if not transcript:
                raise NoTranscriptFound(video_id, languages_to_try)
            text = " ".join([item["text"] for item in transcript])
            return Response({"extracted_text": text})
        except TranscriptsDisabled:
            return Response({"error": "Transcripts are disabled for this YouTube video"}, status=400)
        except Exception as e:
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                available_language_codes = []
                for t in transcript_list:
                    if t.is_generated:
                        available_language_codes.append(f"{t.language_code} (auto-generated)")
                    else:
                        available_language_codes.append(t.language_code)
                return Response({
                    "error": f"YouTube transcript extraction failed. Available languages: {', '.join(available_language_codes)}"
                }, status=400)
            except:
                return Response({"error": f"YouTube transcript extraction failed: {str(e)}"}, status=500)

    if file:
        try:
            file_ext = file.name.split(".")[-1].lower()
            clean_name = sanitize_filename(file.name)
            unique_filename = f"{uuid.uuid4()}-{clean_name}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                for chunk in file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            mime_type, _ = mimetypes.guess_type(temp_path)
            with open(temp_path, 'rb') as f:
                content = f.read()
            try:
                supabase.storage.from_(supabase_bucket).upload(unique_filename, content, {"content-type": mime_type})
                file_url = supabase.storage.from_(supabase_bucket).get_public_url(unique_filename)
            except Exception as e:
                print(f"Supabase upload failed: {e}")
                file_url = None

            if file_ext == "pdf":
                loader = PyPDFLoader(temp_path)
                docs = loader.load()
                extracted_text = "\n".join([doc.page_content for doc in docs])
            elif file_ext == "docx":
                extracted_text = docx_to_text(temp_path)
            elif file_ext == "pptx":
                extracted_text = pptx_to_text(temp_path)
            elif file_ext in ["jpg", "jpeg", "png", "bmp", "tiff", "gif"]:
                extracted_text = image_to_text(temp_path)
            elif file_ext == "txt":
                extracted_text = txt_to_text(temp_path)
            else:
                os.unlink(temp_path)
                return Response({
                    "error": f"Unsupported file format: .{file_ext}",
                    "supported_formats": ["pdf", "docx", "pptx", "jpg", "jpeg", "png", "txt"],
                }, status=400)

            os.unlink(temp_path)
            if not extracted_text.strip():
                return Response({"error": "Text extraction failed or file is empty"}, status=500)

            response_data = {
                "extracted_text": extracted_text
            }
            if file_url:
                response_data["file_info"] = {
                    "filename": unique_filename,
                    "storage_path": unique_filename,
                    "file_url": file_url
                }

            return Response(response_data)
        except Exception as e:
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
            return Response({"error": f"Text extraction failed: {str(e)}"}, status=500)

    return Response({"error": "No file or YouTube URL provided"}, status=400)

@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})
